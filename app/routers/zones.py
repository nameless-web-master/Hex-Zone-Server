"""Router for Zone endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
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


async def check_zone_limit(db: AsyncSession, owner_id: int) -> tuple[bool, int]:
    """Check if owner has reached zone limit."""
    zone_count = await zone_crud.count_zones(db, owner_id)
    return zone_count >= settings.MAX_ZONES_PER_USER, zone_count


@router.post("/", response_model=ZoneResponse, status_code=status.HTTP_201_CREATED)
async def create_zone(
    zone: ZoneCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new zone for the current owner."""
    owner = await owner_crud.get_owner(db, current_user["user_id"])
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
    at_limit, count = await check_zone_limit(db, current_user["user_id"])
    if at_limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Maximum {settings.MAX_ZONES_PER_USER} zones per user reached",
        )
    
    db_zone = await zone_crud.create_zone(db, current_user["user_id"], zone)
    await db.commit()
    return ZoneResponse.model_validate(db_zone)


@router.get("/", response_model=list[ZoneResponse])
async def list_zones(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List zones for the current owner."""
    zones = await zone_crud.list_zones(
        db,
        owner_id=current_user["user_id"],
        skip=skip,
        limit=limit,
    )
    return [ZoneResponse.model_validate(zone) for zone in zones]


@router.get("/{zone_id}", response_model=ZoneResponse)
async def get_zone(
    zone_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a zone by zone_id."""
    zone = await zone_crud.get_zone(db, zone_id, owner_id=current_user["user_id"])
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found",
        )
    return ZoneResponse.model_validate(zone)


@router.patch("/{zone_id}", response_model=ZoneResponse)
async def update_zone(
    zone_id: str,
    zone_update: ZoneUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a zone."""
    owner = await owner_crud.get_owner(db, current_user["user_id"])
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

    zone = await zone_crud.update_zone(
        db,
        zone_id,
        zone_update,
        owner_id=current_user["user_id"],
    )
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found",
        )
    await db.commit()
    return ZoneResponse.model_validate(zone)


@router.delete("/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_zone(
    zone_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a zone."""
    deleted = await zone_crud.delete_zone(db, zone_id, owner_id=current_user["user_id"])
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found",
        )
    await db.commit()
