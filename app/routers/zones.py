"""Router for Zone endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Optional
from app.database import get_db
from app.schemas.schemas import (
    AccountTypeEnum,
    ZoneCreate,
    ZoneResponse,
    ZoneUpdate,
)
from app.crud import zone as zone_crud
from app.crud import owner as owner_crud
from app.core.security import get_current_user
from app.models import Owner
from app.core.config import settings

router = APIRouter(prefix="/zones", tags=["zones"])

PRIVATE_ZONE_TYPES = {
    "warn",
    "alert",
    "geofence",
}


def check_zone_limit(db: Session, owner_id: int) -> tuple[bool, int]:
    """Check if owner has reached zone limit."""
    zone_count = zone_crud.count_zones(db, owner_id)
    return zone_count >= settings.MAX_ZONES_PER_USER, zone_count


@router.post(
    "/",
    response_model=ZoneResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create zone",
    description=(
        "Create Main Zone/Zone #1 or optional zones. Supports zone matching, "
        "H3/grid, geofence, and object-style payloads based on zone_type."
    ),
)
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


@router.get(
    "/",
    response_model=list[ZoneResponse],
    summary="List zones",
    description="List authenticated owner's zones or filter by shared zone_id.",
)
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


@router.patch(
    "/{zone_id}",
    response_model=ZoneResponse,
    summary="Update zone",
    description="Update zone metadata/configuration for the authenticated owner.",
)
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
