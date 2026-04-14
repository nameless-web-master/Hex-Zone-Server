"""Router for Zone endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.schemas.schemas import (
    AccountTypeEnum,
    MessageVisibilityEnum,
    ZoneCreate,
    ZoneMessageCreate,
    ZoneMessageResponse,
    ZoneResponse,
    ZoneUpdate,
)
from app.crud import owner as owner_crud
from app.crud import zone as zone_crud
from app.crud import zone_message as zone_message_crud
from app.core.security import get_current_user
from app.models.zone_message import MessageVisibility, ZoneMessage
from app.core.config import settings

router = APIRouter(prefix="/zones", tags=["zones"])

PRIVATE_ZONE_TYPES = {
    "warn",
    "alert",
    "geofence",
}


def _zone_message_to_response(row: ZoneMessage, zone_uuid: str) -> ZoneMessageResponse:
    return ZoneMessageResponse(
        id=row.id,
        zone_id=zone_uuid,
        sender_id=row.sender_id,
        receiver_id=row.receiver_id,
        visibility=MessageVisibilityEnum(row.visibility.value),
        message=row.message,
        created_at=row.created_at,
    )


def check_zone_limit(db: Session, owner_id: int) -> tuple[bool, int]:
    """Check if owner has reached zone limit."""
    zone_count = zone_crud.count_zones(db, owner_id)
    return zone_count >= settings.MAX_ZONES_PER_USER, zone_count


@router.post("/", response_model=ZoneResponse, status_code=status.HTTP_201_CREATED)
async def create_zone(
    zone: ZoneCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new zone for the current owner."""
    owner = owner_crud.get_owner(db, current_user["user_id"])
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Owner not found",
        )

    if owner.account_type.value == AccountTypeEnum.PRIVATE.value and zone.zone_type not in PRIVATE_ZONE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Private accounts may only create zones of type: {', '.join(sorted(PRIVATE_ZONE_TYPES))}",
        )

    # Check zone limit
    at_limit, count = check_zone_limit(db, current_user["user_id"])
    if at_limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Maximum {settings.MAX_ZONES_PER_USER} zones per user reached",
        )
    
    try:
        db_zone = zone_crud.create_zone(db, current_user["user_id"], zone)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    db.commit()
    created_zone = zone_crud.get_zone_with_geojson(db, db_zone.zone_id, owner_id=current_user["user_id"])
    if not created_zone:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve created zone",
        )
    return ZoneResponse.model_validate(zone_crud.zone_to_dict(created_zone))


@router.get("/", response_model=list[ZoneResponse])
async def list_zones(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    owner_id: Optional[int] = Query(None, ge=1),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List zones for the current owner or a specific owner when provided."""
    if owner_id is not None and owner_id != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: cannot access another owner's zones",
        )

    zones = zone_crud.list_zones_with_geojson(
        db,
        owner_id=owner_id or current_user["user_id"],
        skip=skip,
        limit=limit,
    )
    return [ZoneResponse.model_validate(zone_crud.zone_to_dict(zone)) for zone in zones]


@router.get("/{zone_id}", response_model=ZoneResponse)
async def get_zone(
    zone_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a zone by zone_id."""
    zone = zone_crud.get_zone_with_geojson(db, zone_id, owner_id=current_user["user_id"])
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found",
        )
    return ZoneResponse.model_validate(zone_crud.zone_to_dict(zone))


@router.patch("/{zone_id}", response_model=ZoneResponse)
async def update_zone(
    zone_id: str,
    zone_update: ZoneUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a zone."""
    owner = owner_crud.get_owner(db, current_user["user_id"])
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Owner not found",
        )

    if owner.account_type.value == AccountTypeEnum.PRIVATE.value and zone_update.zone_type is not None and zone_update.zone_type not in PRIVATE_ZONE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Private accounts may only create zones of type: {', '.join(sorted(PRIVATE_ZONE_TYPES))}",
        )

    try:
        zone = zone_crud.update_zone(
            db,
            zone_id,
            zone_update,
            owner_id=current_user["user_id"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found",
        )
    db.commit()
    updated_zone = zone_crud.get_zone_with_geojson(db, zone_id, owner_id=current_user["user_id"])
    if not updated_zone:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve updated zone",
        )
    return ZoneResponse.model_validate(zone_crud.zone_to_dict(updated_zone))


@router.delete("/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_zone(
    zone_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a zone."""
    deleted = zone_crud.delete_zone(db, zone_id, owner_id=current_user["user_id"])
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found",
        )
    db.commit()


@router.post(
    "/{zone_id}/messages",
    response_model=ZoneMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_zone_message(
    zone_id: str,
    body: ZoneMessageCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Post a public or private message in a zone. Sender is the authenticated owner."""
    zone = zone_crud.get_zone(db, zone_id=zone_id)
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found",
        )

    sender_id = current_user["user_id"]

    if body.visibility == MessageVisibilityEnum.PUBLIC:
        if body.receiver_id is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Public messages must not include receiver_id",
            )
        receiver_id = None
        vis = MessageVisibility.PUBLIC
    else:
        if body.receiver_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Private messages require receiver_id",
            )
        receiver_id = body.receiver_id
        if receiver_id == sender_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Private message receiver_id must differ from sender",
            )
        receiver = owner_crud.get_owner(db, receiver_id)
        if not receiver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Receiver not found",
            )
        vis = MessageVisibility.PRIVATE

    row = zone_message_crud.create_zone_message(
        db,
        zone_internal_id=zone.id,
        sender_id=sender_id,
        message=body.message,
        visibility=vis,
        receiver_id=receiver_id,
    )
    db.commit()
    db.refresh(row)
    return _zone_message_to_response(row, zone.zone_id)


@router.get("/{zone_id}/messages", response_model=list[ZoneMessageResponse])
async def list_zone_messages(
    zone_id: str,
    with_owner_id: Optional[int] = Query(
        None,
        ge=1,
        description="If set, include all public messages plus only private messages between you and this owner",
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List messages visible to the authenticated owner.

    Always returns every **public** message in the zone, plus **private** messages
    where you are the sender or receiver. If ``with_owner_id`` is set, private
    messages are limited to the thread with that owner (public messages are still
    all included).
    """
    zone = zone_crud.get_zone(db, zone_id=zone_id)
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found",
        )

    viewer = current_user["user_id"]
    rows = zone_message_crud.list_zone_messages_for_viewer(
        db,
        zone_internal_id=zone.id,
        viewer_owner_id=viewer,
        with_owner_id=with_owner_id,
        skip=skip,
        limit=limit,
    )
    return [_zone_message_to_response(r, zone.zone_id) for r in rows]
