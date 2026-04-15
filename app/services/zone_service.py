"""Zone service."""
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.crud import owner as owner_crud
from app.crud import zone as zone_crud
from app.schemas.schemas import AccountTypeEnum, ZoneCreate, ZoneUpdate

PRIVATE_ZONE_TYPES = {"warn", "alert", "geofence", "polygon", "circle", "grid", "dynamic", "proximity", "object"}


def _validate_owner_zone_type(db: Session, owner_id: int, zone_type: str) -> None:
    owner = owner_crud.get_owner(db, owner_id)
    if not owner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Owner not found")
    if owner.account_type.value == AccountTypeEnum.PRIVATE.value and zone_type not in PRIVATE_ZONE_TYPES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Zone type not allowed for account")


def create_zone(db: Session, owner_id: int, payload: ZoneCreate):
    """Create zone while enforcing per-user limit."""
    _validate_owner_zone_type(db, owner_id, str(payload.zone_type))
    if zone_crud.count_zones(db, owner_id) >= settings.MAX_ZONES_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Maximum {settings.MAX_ZONES_PER_USER} zones per user reached",
        )
    try:
        zone = zone_crud.create_zone(db, owner_id, payload)
        db.commit()
        return zone_crud.get_zone_with_geojson(db, zone.zone_id, owner_id=owner_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Zone ID already exists")


def update_zone(db: Session, owner_id: int, zone_id: str, payload: ZoneUpdate):
    """Update zone for owner."""
    if payload.zone_type is not None:
        _validate_owner_zone_type(db, owner_id, str(payload.zone_type))
    zone = zone_crud.update_zone(db, zone_id, payload, owner_id=owner_id)
    if not zone:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found")
    db.commit()
    return zone_crud.get_zone_with_geojson(db, zone_id, owner_id=owner_id)
