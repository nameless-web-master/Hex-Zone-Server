"""Router for Zone endpoints."""
# UPDATED for Zoning-Messaging-System-Summary-v1.1.pdf
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Optional
from app.database import get_db
from app.schemas.schemas import (
    AccountTypeEnum,
    ZoneTypeEnum,
    ZoneCreate,
    ZoneResponse,
    ZoneUpdate,
)
from app.crud import zone as zone_crud
from app.crud import owner as owner_crud
from app.core.security import get_current_user

router = APIRouter(prefix="/zones", tags=["zones"])

ALL_ZONE_TYPES = {zone_type.value for zone_type in ZoneTypeEnum}
ZONE_LIMITS_BY_ACCOUNT = {
    AccountTypeEnum.PRIVATE.value: 3,
    AccountTypeEnum.EXCLUSIVE.value: 3,
    AccountTypeEnum.GUARD.value: 1,
}


def check_zone_limit(db: Session, owner_id: int, account_type: str) -> tuple[bool, int, int]:
    """Check if owner has reached zone limit."""
    zone_count = zone_crud.count_zones(db, owner_id)
    limit = ZONE_LIMITS_BY_ACCOUNT.get(account_type, 3)
    return zone_count >= limit, zone_count, limit


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

    if zone.zone_type.value not in ALL_ZONE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported zone type: {zone.zone_type.value}",
        )

    # Check zone limit
    at_limit, count, limit = check_zone_limit(db, current_user["user_id"], owner.account_type)
    if at_limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Maximum {limit} zones per user reached for {owner.account_type} accounts",
        )
    
    try:
        db_zone = zone_crud.create_zone(db, current_user["user_id"], zone)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except IntegrityError as exc:
        db.rollback()
        if "zone_id" in str(exc).lower() and "unique" in str(exc).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Zone ID already exists",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid zone payload",
        )

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
    zone_id: Optional[str] = Query(None, min_length=1),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List zones, or all matching shared zone_id entries when provided."""
    if zone_id is not None:
        zones = zone_crud.list_zones_by_zone_id_with_geojson(
            db,
            zone_id=zone_id,
            skip=skip,
            limit=limit,
        )
        return [ZoneResponse.model_validate(zone_crud.zone_to_dict(zone)) for zone in zones]

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


@router.get("/{zone_id}", response_model=list[ZoneResponse])
async def get_zone(
    zone_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all zones by shared zone_id for authenticated users."""
    zones = zone_crud.list_zones_by_zone_id_with_geojson(db, zone_id)
    if not zones:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found",
        )
    return [ZoneResponse.model_validate(zone_crud.zone_to_dict(zone)) for zone in zones]


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

    if zone_update.zone_type is not None and zone_update.zone_type.value not in ALL_ZONE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported zone type: {zone_update.zone_type.value}",
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
