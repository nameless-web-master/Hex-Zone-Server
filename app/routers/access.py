"""Public QR guest access and administrator approve/reject."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.crud import owner as owner_crud
from app.database import get_db
from app.models import GuestAccessSession
from app.schemas.access_guest import (
    GuestAccessHttpError,
    GuestAdminDecisionResponse,
    GuestArrivalRequest,
    GuestScanResponse,
    GuestSessionPollResponse,
    GuestZoneActionRequest,
)
from app.services import guest_access_service
from app.websocket.manager import ws_manager

router = APIRouter(prefix="/api/access", tags=["access"])

_PERM_SUMMARY = "Guest arrival (QR scan)"
_PERM_DESCRIPTION = """
No authentication. Validates that **zone_id** exists, finds an **active access schedule**
whose window contains server time and matches **event_id** (if sent) **or** **guest_name**,
then:

- **EXPECTED**: persist a guest session, write a PERMISSION zone event, push WebSocket **`guest_is_here`**
  to the schedule creator (and optionally all zone administrators when `notify_member_assist` is set on the schedule).
- **UNEXPECTED**: persist a pending session, push WebSocket **`unexpected_guest`** to all active owners
  sharing **zone_id**, and record a CHAT-shaped zone event as an admin↔guest thread anchor.

Returns **guest_id** for polling (`GET /api/access/session/{guest_id}`).
"""


@router.post(
    "/permission",
    response_model=GuestScanResponse,
    status_code=status.HTTP_200_OK,
    summary=_PERM_SUMMARY,
    description=_PERM_DESCRIPTION.strip(),
    response_description="Guest-facing outcome plus opaque guest_id for polling.",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Unknown or inactive zone (`error_code`: **INVALID_ZONE**).",
            "model": GuestAccessHttpError,
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": (
                "Request validation failure **or** zone has no resolvable administrator (**NO_ZONE_ADMIN**); "
                "see `error_code` in body."
            ),
            "model": GuestAccessHttpError,
        },
    },
)
async def guest_permission(payload: GuestArrivalRequest, db: Session = Depends(get_db)):
    lat = payload.location.lat if payload.location else None
    lng = payload.location.lng if payload.location else None
    result = guest_access_service.process_guest_arrival(
        db,
        zone_id=payload.zone_id.strip(),
        guest_name=payload.guest_name,
        event_id=payload.event_id,
        device_id=payload.device_id,
        latitude=lat,
        longitude=lng,
    )
    if result.get("error"):
        raise HTTPException(
            status_code=result["http_status"],
            detail={"error_code": result["error"], "message": result["message"]},
        )
    db.commit()

    for user_ids, event_payload in result.get("ws_guest_is_here") or []:
        await ws_manager.broadcast_to_users(user_ids, "guest_is_here", event_payload)
    for user_ids, event_payload in result.get("ws_unexpected_guest") or []:
        await ws_manager.broadcast_to_users(user_ids, "unexpected_guest", event_payload)

    return GuestScanResponse.model_validate(result["guest_response"])


@router.get(
    "/session/{guest_id}",
    response_model=GuestSessionPollResponse,
    status_code=status.HTTP_200_OK,
    summary="Poll guest session status",
    description=(
        "Public poll for guest clients without a WebSocket. Supply **guest_id** from "
        "POST /api/access/permission and the same **zone_id** query parameter used at arrival."
    ),
    response_description="Guest-visible status and instructional message.",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "No session for this guest_id + zone_id pair.",
            "model": GuestAccessHttpError,
        },
    },
)
async def guest_session_status(
    guest_id: str,
    zone_id: str = Query(
        ...,
        min_length=1,
        max_length=100,
        description="Must match the zone_id submitted at arrival.",
    ),
    db: Session = Depends(get_db),
):
    row = (
        db.query(GuestAccessSession)
        .filter(GuestAccessSession.guest_id == guest_id, GuestAccessSession.zone_id == zone_id.strip())
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "NOT_FOUND", "message": "Unknown guest session."},
        )
    return GuestSessionPollResponse.model_validate(guest_access_service.guest_session_public_view(row))


@router.post(
    "/approve",
    response_model=GuestAdminDecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve unexpected guest",
    description=(
        "Requires **Bearer** JWT. Caller must be an **administrator** with **owner.zone_id** equal to "
        "**zone_id**. Only unexpected arrivals in **pending** state can be approved."
    ),
    response_description="Resolution copied from audit message; guest learns via polling.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid bearer token."},
        status.HTTP_403_FORBIDDEN: {
            "description": "Caller is not a zone administrator (`FORBIDDEN`).",
            "model": GuestAccessHttpError,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Owner not found or guest session not found (`NOT_FOUND`).",
            "model": GuestAccessHttpError,
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Session not unexpected or already resolved (`INVALID_STATE`).",
            "model": GuestAccessHttpError,
        },
    },
)
async def approve_guest(
    payload: GuestZoneActionRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    owner = owner_crud.get_owner(db, current_user["user_id"])
    if not owner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Owner not found")

    result = guest_access_service.approve_guest(
        db,
        acting_owner=owner,
        zone_id=payload.zone_id.strip(),
        guest_id=payload.guest_id.strip(),
    )
    if result.get("error"):
        raise HTTPException(
            status_code=result["http_status"],
            detail={"error_code": result["error"], "message": result["message"]},
        )
    db.commit()
    return GuestAdminDecisionResponse.model_validate(result["guest_response"])


@router.post(
    "/reject",
    response_model=GuestAdminDecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject unexpected guest",
    description=(
        "Same authorization rules as **approve**. Sets resolution to rejected; guest observes "
        "via GET /api/access/session/{guest_id}."
    ),
    response_description="Resolution payload for admin client.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid bearer token."},
        status.HTTP_403_FORBIDDEN: {
            "description": "Caller is not a zone administrator (`FORBIDDEN`).",
            "model": GuestAccessHttpError,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Owner not found or guest session not found (`NOT_FOUND`).",
            "model": GuestAccessHttpError,
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Session not unexpected or already resolved (`INVALID_STATE`).",
            "model": GuestAccessHttpError,
        },
    },
)
async def reject_guest(
    payload: GuestZoneActionRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    owner = owner_crud.get_owner(db, current_user["user_id"])
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "NOT_FOUND", "message": "Owner not found"},
        )

    result = guest_access_service.reject_guest(
        db,
        acting_owner=owner,
        zone_id=payload.zone_id.strip(),
        guest_id=payload.guest_id.strip(),
    )
    if result.get("error"):
        raise HTTPException(
            status_code=result["http_status"],
            detail={"error_code": result["error"], "message": result["message"]},
        )
    db.commit()
    return GuestAdminDecisionResponse.model_validate(result["guest_response"])
