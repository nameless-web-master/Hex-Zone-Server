"""Advanced geo propagation and permission APIs."""
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.crud import owner as owner_crud
from app.database import get_db
from app.models import AccessSchedule, MessageBlock, ZoneMessageEvent
from app.schemas.message_feature import (
    AccessScheduleCreate,
    AccessScheduleResponse,
    BlockRuleCreate,
    BlockRuleResponse,
    PermissionDecisionResponse,
    PropagationMessageCreate,
    PropagationMessageResponse,
)
from app.services import message_feature_service, permission_service
from app.services.zone_membership_service import refresh_owner_memberships
from app.websocket.manager import ws_manager

router = APIRouter(prefix="/message-feature", tags=["message-feature"])


@router.post("/members/location", summary="Update member location and zone memberships")
async def update_member_location(
    payload: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sender = owner_crud.get_owner(db, current_user["user_id"])
    if not sender:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sender owner not found")

    latitude = payload.get("latitude")
    longitude = payload.get("longitude")
    if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="latitude/longitude are required")

    matched = refresh_owner_memberships(db, sender, float(latitude), float(longitude))
    db.commit()
    return {"zone_ids": matched}


@router.post("/messages/propagate", response_model=PropagationMessageResponse, status_code=status.HTTP_201_CREATED)
async def create_geo_message(
    payload: PropagationMessageCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sender = owner_crud.get_owner(db, current_user["user_id"])
    if not sender:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sender owner not found")

    if payload.type.value == "PERMISSION":
        permission_result = permission_service.process_permission_message(db, sender, payload)
        db.commit()
        await ws_manager.broadcast_to_users(
            permission_result["delivered_owner_ids"],
            "PERMISSION_MESSAGE",
            permission_result,
        )
        return {
            "id": "permission-flow",
            "type": "PERMISSION",
            "category": "Access",
            "scope": "private",
            "zone_ids": [payload.to or sender.zone_id],
            "delivered_owner_ids": permission_result["delivered_owner_ids"],
            "blocked_owner_ids": [],
            "created_at": payload.tt.isoformat(),
        }

    try:
        result = message_feature_service.create_geo_propagated_message(db, sender, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "MISSING_RECIPIENT_FOR_PRIVATE_TYPE",
                "message": "receiver_owner_id is required for private-scope message types.",
            },
        ) from exc
    db.commit()

    await ws_manager.broadcast_to_users(result["delivered_owner_ids"], "NEW_GEO_MESSAGE", result)
    return result


@router.post(
    "/messages/ingest",
    response_model=PropagationMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Device ingest endpoint using API key",
)
async def create_geo_message_with_api_key(
    payload: PropagationMessageCreate,
    x_api_key: str = Header(..., alias="x-api-key"),
    db: Session = Depends(get_db),
):
    sender = owner_crud.get_owner_by_api_key(db, x_api_key)
    if not sender:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    if payload.type.value == "PERMISSION":
        permission_result = permission_service.process_permission_message(db, sender, payload)
        db.commit()
        await ws_manager.broadcast_to_users(
            permission_result["delivered_owner_ids"],
            "PERMISSION_MESSAGE",
            permission_result,
        )
        return {
            "id": "permission-flow",
            "type": "PERMISSION",
            "category": "Access",
            "scope": "private",
            "zone_ids": [payload.to or sender.zone_id],
            "delivered_owner_ids": permission_result["delivered_owner_ids"],
            "blocked_owner_ids": [],
            "created_at": payload.tt.isoformat(),
        }

    try:
        result = message_feature_service.create_geo_propagated_message(db, sender, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "MISSING_RECIPIENT_FOR_PRIVATE_TYPE",
                "message": "receiver_owner_id is required for private-scope message types.",
            },
        ) from exc
    db.commit()
    await ws_manager.broadcast_to_users(result["delivered_owner_ids"], "NEW_GEO_MESSAGE", result)
    return result


@router.post("/blocks", response_model=BlockRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_block_rule(
    payload: BlockRuleCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    block = MessageBlock(
        owner_id=current_user["user_id"],
        blocked_owner_id=payload.blocked_owner_id,
        blocked_message_type=(payload.blocked_message_type.value if payload.blocked_message_type else None),
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    return block


@router.get("/blocks", response_model=list[BlockRuleResponse])
async def list_block_rules(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(MessageBlock)
        .filter(MessageBlock.owner_id == current_user["user_id"])
        .order_by(MessageBlock.created_at.desc())
        .all()
    )
    return rows


@router.delete("/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block_rule(
    block_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.get(MessageBlock, block_id)
    if not row or row.owner_id != current_user["user_id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block rule not found")
    db.delete(row)
    db.commit()


@router.post(
    "/access/schedules",
    response_model=AccessScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create access schedule",
    description=(
        "Authenticated member defines an expected visitor window for a **zone_id**. "
        "Used by matching logic in `POST /api/access/permission` (QR guests) and by "
        "`process_permission_message` for device-originated PERMISSION messages."
    ),
    response_description="Persisted schedule including audit fields.",
)
async def create_access_schedule(
    payload: AccessScheduleCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner = owner_crud.get_owner(db, current_user["user_id"])
    if not owner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Owner not found")
    schedule = permission_service.create_schedule(db, owner, payload.model_dump())
    db.commit()
    db.refresh(schedule)
    return schedule


@router.get(
    "/access/schedules",
    response_model=list[AccessScheduleResponse],
    summary="List access schedules",
    description="Returns active schedules, optionally filtered by **zone_id**.",
    response_description="Newest-first list of schedule rows.",
)
async def list_access_schedules(
    zone_id: str | None = Query(default=None, description="If set, restrict to this zone id."),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = current_user
    query = db.query(AccessSchedule).filter(AccessSchedule.active.is_(True))
    if zone_id:
        query = query.filter(AccessSchedule.zone_id == zone_id)
    return query.order_by(AccessSchedule.created_at.desc()).all()


@router.get("/messages/new")
async def list_new_feature_messages(
    since: str = Query(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = current_user
    try:
        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid since cursor") from exc
    rows = (
        db.query(ZoneMessageEvent)
        .filter(ZoneMessageEvent.created_at >= since_dt)
        .order_by(ZoneMessageEvent.created_at.asc())
        .limit(500)
        .all()
    )
    return [
        {
            "id": row.id,
            "zoneId": row.zone_id,
            "type": row.type,
            "category": row.category.value,
            "scope": row.scope.value,
            "text": row.text,
            "body": row.body_json,
            "metadata": row.metadata_json,
            "createdAt": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.post(
    "/access/permission",
    response_model=PermissionDecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Process PERMISSION propagation (authenticated)",
    description=(
        "Requires JWT. **type** must be `PERMISSION`. Evaluates schedules for **payload.to** "
        "(or sender zone), emits `ZoneMessageEvent`, and broadcasts **`PERMISSION_MESSAGE`** "
        "to `delivered_owner_ids`. Public QR scans without login should call **`POST /api/access/permission`** instead."
    ),
    response_description="Decision bundle plus websocket fan-out targets.",
)
async def process_permission(
    payload: PropagationMessageCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.type.value != "PERMISSION":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="type must be PERMISSION")
    sender = owner_crud.get_owner(db, current_user["user_id"])
    if not sender:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sender owner not found")
    result = permission_service.process_permission_message(db, sender, payload)
    db.commit()
    await ws_manager.broadcast_to_users(result["delivered_owner_ids"], "PERMISSION_MESSAGE", result)
    return result
