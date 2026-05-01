"""Public QR guest access and administrator approve/reject."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.guest_permission_rate_limit import allow_request
from app.core.security import get_current_user
from app.crud import owner as owner_crud
from app.database import get_db
from app.models import GuestAccessSession
from app.models.owner import Owner, OwnerRole
from app.schemas.access_guest import (
    GuestAccessHttpError,
    GuestAccessQrLinkResponse,
    GuestAdminDecisionResponse,
    GuestArrivalRequest,
    GuestQrTokenCreate,
    GuestQrTokenCreatedResponse,
    GuestQrTokenLinkBundle,
    GuestQrTokenListItem,
    GuestScanResponse,
    GuestSessionPollResponse,
    GuestZoneActionRequest,
)
from app.services import guest_access_qr, guest_access_qr_token_service, guest_access_service
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/access", tags=["access"])

_PERM_SUMMARY = "Guest arrival (QR scan)"
_PERM_DESCRIPTION = """
No authentication. Supply either **zone_id** (static QR `?zid=`) or **guest_qr_token** (issued QR `?gt=`).

Validates that **zone_id** exists (explicit or resolved from token), finds an **active access schedule**
whose window contains server time and matches **event_id** (if sent) **or** **guest_name**,
then:

- **EXPECTED**: persist a guest session, write a PERMISSION zone event, push WebSocket **`guest_is_here`**
  to the schedule creator (and optionally all zone administrators when `notify_member_assist` is set on the schedule).
- **UNEXPECTED**: persist a pending session, push WebSocket **`unexpected_guest`** to all active owners
  sharing **zone_id**, and record a CHAT-shaped zone event as an admin↔guest thread anchor.

Returns **guest_id** for polling (`GET /api/access/session/{guest_id}`).

Backend-issued tokens (`POST /api/access/qr-tokens`) may enforce expiry, revocation, and optional **max_uses** (counted on successful arrivals only).

Rate-limited per client IP (rolling minute). CORS: browser guests should call the API from an allowed origin (this server enables permissive CORS by default).
"""


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _require_guest_qr_administrator(db: Session, current_user: dict, zone_id: str) -> Owner:
    owner = owner_crud.get_owner(db, current_user["user_id"])
    if not owner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Owner not found")
    zid = zone_id.strip()
    if owner.zone_id != zid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "FORBIDDEN",
                "message": "You may only request guest QR links for your own zone.",
            },
        )
    if owner.role != OwnerRole.ADMINISTRATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "FORBIDDEN",
                "message": "Administrator role required to fetch guest access QR material.",
            },
        )
    return owner


@router.post(
    "/permission",
    response_model=GuestScanResponse,
    status_code=status.HTTP_200_OK,
    summary=_PERM_SUMMARY,
    description=_PERM_DESCRIPTION.strip(),
    response_description="Guest-facing outcome plus opaque guest_id for polling.",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Unknown zone (**INVALID_ZONE**) or unknown guest QR token (**INVALID_TOKEN**).",
            "model": GuestAccessHttpError,
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": (
                "Validation failure, **NO_ZONE_ADMIN**, **ZONE_MISMATCH**, **EVENT_MISMATCH**, "
                "or related errors; see `error_code` in body."
            ),
            "model": GuestAccessHttpError,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": (
                "Guest QR token revoked, expired, or depleted (**TOKEN_REVOKED**, **TOKEN_EXPIRED**, **TOKEN_DEPLETED**)."
            ),
            "model": GuestAccessHttpError,
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "description": "Too many anonymous arrivals from this client (**RATE_LIMITED**).",
            "model": GuestAccessHttpError,
        },
    },
)
async def guest_permission(request: Request, payload: GuestArrivalRequest, db: Session = Depends(get_db)):
    ip_key = _client_ip(request)
    if not allow_request(
        f"guest_perm:{ip_key}",
        max_events=settings.GUEST_ACCESS_PERMISSION_MAX_PER_MINUTE,
        window_seconds=60.0,
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error_code": "RATE_LIMITED",
                "message": "Too many arrival attempts from this network. Please wait and try again.",
            },
        )

    qr_row = None
    raw_gt = (payload.guest_qr_token or "").strip()
    payload_zone = (payload.zone_id or "").strip() or None
    effective_zone_id = payload_zone
    effective_event_id = payload.event_id

    if raw_gt:
        qr_row = guest_access_qr_token_service.lock_guest_qr_token_row(db, raw_gt)
        verr = guest_access_qr_token_service.validate_locked_guest_qr_token(qr_row)
        if verr:
            logger.info(
                "guest_access_permission guest_qr_token outcome=error error_code=%s",
                verr["error"],
            )
            raise HTTPException(
                status_code=verr["http_status"],
                detail={"error_code": verr["error"], "message": verr["message"]},
            )

        tz_zone = qr_row.zone_id
        if payload_zone and payload_zone != tz_zone:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error_code": "ZONE_MISMATCH",
                    "message": "zone_id does not match the guest QR token.",
                },
            )
        effective_zone_id = tz_zone

        merged_ev, eerr = guest_access_qr_token_service.merge_event_id_for_arrival(
            token_event_id=qr_row.event_id,
            payload_event_id=payload.event_id,
        )
        if eerr:
            raise HTTPException(
                status_code=eerr["http_status"],
                detail={"error_code": eerr["error"], "message": eerr["message"]},
            )
        effective_event_id = merged_ev

    elif not effective_zone_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "MISSING_ZONE",
                "message": "zone_id is required when guest_qr_token is omitted.",
            },
        )

    lat = payload.location.lat if payload.location else None
    lng = payload.location.lng if payload.location else None

    result = guest_access_service.process_guest_arrival(
        db,
        zone_id=effective_zone_id,
        guest_name=payload.guest_name,
        event_id=effective_event_id,
        device_id=payload.device_id,
        latitude=lat,
        longitude=lng,
        qr_token_db_id=qr_row.id if qr_row else None,
    )
    if result.get("error"):
        logger.info(
            "guest_access_permission zone_id=%s outcome=error error_code=%s",
            effective_zone_id,
            result["error"],
        )
        raise HTTPException(
            status_code=result["http_status"],
            detail={"error_code": result["error"], "message": result["message"]},
        )

    gr = result["guest_response"]
    logger.info(
        "guest_access_permission zone_id=%s outcome=%s guest_id=%s",
        effective_zone_id,
        gr["status"],
        gr["guest_id"],
    )

    if qr_row:
        guest_access_qr_token_service.apply_successful_arrival_use(db, qr_row)

    db.commit()

    for user_ids, event_payload in result.get("ws_guest_is_here") or []:
        await ws_manager.broadcast_to_users(user_ids, "guest_is_here", event_payload)
    for user_ids, event_payload in result.get("ws_unexpected_guest") or []:
        await ws_manager.broadcast_to_users(user_ids, "unexpected_guest", event_payload)

    return GuestScanResponse.model_validate(gr)


@router.get(
    "/qr-link",
    response_model=GuestAccessQrLinkResponse,
    status_code=status.HTTP_200_OK,
    summary="Canonical guest-access deep link",
    description=(
        "Requires **Bearer** JWT. Caller must be a **zone administrator** with **owner.zone_id** equal "
        "to **zone_id**. Returns the stable SPA path **`/access?zid=`** (optional **`eid=`**), and an absolute "
        "**url** when **GUEST_ACCESS_APP_BASE_URL** is configured. "
        "This is **not** the member-invite flow (`POST /utils/qr/generate`)."
    ),
    response_description="URL for QR encoding (no PII in query string).",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid bearer token."},
        status.HTTP_403_FORBIDDEN: {
            "description": "Wrong zone or not an administrator.",
            "model": GuestAccessHttpError,
        },
        status.HTTP_404_NOT_FOUND: {"description": "Authenticated owner not found."},
    },
)
async def guest_access_qr_link(
    zone_id: str = Query(..., min_length=1, max_length=100, description="Hex zone id encoded as `zid`."),
    event_id: str | None = Query(
        default=None,
        max_length=100,
        description="Optional; included as `eid` so guests are pre-associated with an event id.",
    ),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _ = _require_guest_qr_administrator(db, current_user, zone_id)
    zid = zone_id.strip()
    path = guest_access_qr.guest_access_path_with_query(zid, event_id)
    absolute = guest_access_qr.guest_access_absolute_url(zid, event_id)
    return GuestAccessQrLinkResponse(url=absolute, zone_id=zid, path_with_query=path)


@router.get(
    "/qr.png",
    summary="PNG QR code for guest-access URL",
    description=(
        "Same authorization as **GET /api/access/qr-link**. Returns **image/png** bytes encoding the "
        "same absolute URL as **qr-link**. Requires **GUEST_ACCESS_APP_BASE_URL** (or legacy **PUBLIC_WEB_APP_URL**) "
        "so the encoded URL is absolute."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid bearer token."},
        status.HTTP_403_FORBIDDEN: {"description": "Wrong zone or not an administrator.", "model": GuestAccessHttpError},
        status.HTTP_404_NOT_FOUND: {"description": "Authenticated owner not found."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Web app base URL not configured (**GUEST_LINK_BASE_UNCONFIGURED**).",
            "model": GuestAccessHttpError,
        },
    },
    response_class=Response,
)
async def guest_access_qr_png(
    zone_id: str = Query(..., min_length=1, max_length=100),
    event_id: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _ = _require_guest_qr_administrator(db, current_user, zone_id)
    zid = zone_id.strip()
    url = guest_access_qr.guest_access_absolute_url(zid, event_id)
    if not url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "GUEST_LINK_BASE_UNCONFIGURED",
                "message": "Set GUEST_ACCESS_APP_BASE_URL so the API can build an absolute guest URL for the QR image.",
            },
        )
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "GUEST_LINK_BASE_INVALID",
                "message": "GUEST_ACCESS_APP_BASE_URL must start with http:// or https://.",
            },
        )

    png = guest_access_qr.qr_png_bytes_for_url(url)
    return Response(
        content=png,
        media_type="image/png",
        headers={
            "Cache-Control": "private, max-age=300",
        },
    )


@router.post(
    "/qr-tokens",
    response_model=GuestQrTokenCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create stored guest QR token",
    description=(
        "**Bearer** JWT; **administrator** for **zone_id**. Mints an opaque **guest_qr_token** used in "
        "`POST /api/access/permission` and SPA **`/access?gt=`**. Default TTL **168h** if neither "
        "**expires_at** nor **expires_in_hours** is sent."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid bearer token."},
        status.HTTP_403_FORBIDDEN: {"model": GuestAccessHttpError},
        status.HTTP_404_NOT_FOUND: {"description": "Owner not found.", "model": GuestAccessHttpError},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": GuestAccessHttpError},
    },
)
async def create_guest_access_qr_token(
    payload: GuestQrTokenCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    owner = owner_crud.get_owner(db, current_user["user_id"])
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "NOT_FOUND", "message": "Owner not found"},
        )
    result = guest_access_qr_token_service.create_guest_qr_token(
        db,
        owner,
        zone_id=payload.zone_id,
        expires_at=payload.expires_at,
        expires_in_hours=payload.expires_in_hours,
        event_id=payload.event_id,
        label=payload.label,
        max_uses=payload.max_uses,
    )
    if result.get("error"):
        raise HTTPException(
            status_code=result["http_status"],
            detail={"error_code": result["error"], "message": result["message"]},
        )
    row = result["row"]
    db.commit()
    db.refresh(row)
    path = guest_access_qr.guest_access_path_with_guest_token(row.token)
    url = guest_access_qr.guest_access_absolute_url_with_guest_token(row.token)
    body = {
        **guest_access_qr_token_service.serialize_guest_qr_token_public(row),
        "token": row.token,
        "url": url,
        "path_with_query": path,
    }
    return GuestQrTokenCreatedResponse.model_validate(body)


@router.get(
    "/qr-tokens",
    response_model=list[GuestQrTokenListItem],
    summary="List stored guest QR tokens",
    description="**Administrator** JWT; **zone_id** query must match caller **owner.zone_id**.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid bearer token."},
        status.HTTP_403_FORBIDDEN: {"model": GuestAccessHttpError},
        status.HTTP_404_NOT_FOUND: {"model": GuestAccessHttpError},
    },
)
async def list_guest_access_qr_tokens(
    zone_id: str = Query(..., min_length=1, max_length=100),
    include_revoked: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    owner = owner_crud.get_owner(db, current_user["user_id"])
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "NOT_FOUND", "message": "Owner not found"},
        )
    result = guest_access_qr_token_service.list_guest_qr_tokens(
        db,
        owner,
        zone_id=zone_id.strip(),
        limit=limit,
        include_revoked=include_revoked,
    )
    if result.get("error"):
        raise HTTPException(
            status_code=result["http_status"],
            detail={"error_code": result["error"], "message": result["message"]},
        )
    return [
        GuestQrTokenListItem.model_validate(guest_access_qr_token_service.serialize_guest_qr_token_public(r))
        for r in result["rows"]
    ]


@router.post(
    "/qr-tokens/{qr_token_id}/revoke",
    response_model=GuestQrTokenListItem,
    summary="Revoke a stored guest QR token",
    description="Token stops accepting new arrivals immediately.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid bearer token."},
        status.HTTP_403_FORBIDDEN: {"model": GuestAccessHttpError},
        status.HTTP_404_NOT_FOUND: {"model": GuestAccessHttpError},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": GuestAccessHttpError},
    },
)
async def revoke_guest_access_qr_token(
    qr_token_id: int,
    zone_id: str = Query(..., min_length=1, max_length=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    owner = owner_crud.get_owner(db, current_user["user_id"])
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "NOT_FOUND", "message": "Owner not found"},
        )
    result = guest_access_qr_token_service.revoke_guest_qr_token(
        db,
        owner,
        zone_id=zone_id.strip(),
        token_row_id=qr_token_id,
    )
    if result.get("error"):
        raise HTTPException(
            status_code=result["http_status"],
            detail={"error_code": result["error"], "message": result["message"]},
        )
    row = result["row"]
    db.commit()
    db.refresh(row)
    return GuestQrTokenListItem.model_validate(guest_access_qr_token_service.serialize_guest_qr_token_public(row))


@router.get(
    "/qr-tokens/{qr_token_id}/link",
    response_model=GuestQrTokenLinkBundle,
    summary="Resolve URL for stored guest QR token",
    description="Returns absolute **url** when web base env is set (same rules as **GET /api/access/qr-link**).",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid bearer token."},
        status.HTTP_403_FORBIDDEN: {"model": GuestAccessHttpError},
        status.HTTP_404_NOT_FOUND: {"model": GuestAccessHttpError},
    },
)
async def guest_access_qr_token_link(
    qr_token_id: int,
    zone_id: str = Query(..., min_length=1, max_length=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    owner = owner_crud.get_owner(db, current_user["user_id"])
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "NOT_FOUND", "message": "Owner not found"},
        )
    result = guest_access_qr_token_service.get_guest_qr_token_row_admin(
        db,
        owner,
        zone_id=zone_id.strip(),
        token_row_id=qr_token_id,
    )
    if result.get("error"):
        raise HTTPException(
            status_code=result["http_status"],
            detail={"error_code": result["error"], "message": result["message"]},
        )
    row = result["row"]
    path = guest_access_qr.guest_access_path_with_guest_token(row.token)
    url = guest_access_qr.guest_access_absolute_url_with_guest_token(row.token)
    return GuestQrTokenLinkBundle(id=row.id, url=url, path_with_query=path)


@router.get(
    "/qr-tokens/{qr_token_id}/qr.png",
    summary="PNG QR for stored guest token URL",
    description="Same as **GET /api/access/qr.png** but for a DB-backed token row.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid bearer token."},
        status.HTTP_403_FORBIDDEN: {"model": GuestAccessHttpError},
        status.HTTP_404_NOT_FOUND: {"model": GuestAccessHttpError},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": GuestAccessHttpError},
    },
    response_class=Response,
)
async def guest_access_qr_token_png(
    qr_token_id: int,
    zone_id: str = Query(..., min_length=1, max_length=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    owner = owner_crud.get_owner(db, current_user["user_id"])
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "NOT_FOUND", "message": "Owner not found"},
        )
    result = guest_access_qr_token_service.get_guest_qr_token_row_admin(
        db,
        owner,
        zone_id=zone_id.strip(),
        token_row_id=qr_token_id,
    )
    if result.get("error"):
        raise HTTPException(
            status_code=result["http_status"],
            detail={"error_code": result["error"], "message": result["message"]},
        )
    row = result["row"]
    url = guest_access_qr.guest_access_absolute_url_with_guest_token(row.token)
    if not url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "GUEST_LINK_BASE_UNCONFIGURED",
                "message": "Set GUEST_ACCESS_APP_BASE_URL so the API can build an absolute guest URL for the QR image.",
            },
        )
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "GUEST_LINK_BASE_INVALID",
                "message": "GUEST_ACCESS_APP_BASE_URL must start with http:// or https://.",
            },
        )
    png = guest_access_qr.qr_png_bytes_for_url(url)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=300"},
    )


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
