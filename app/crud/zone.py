"""CRUD operations for Zone."""
from sqlalchemy.orm import Session
from sqlalchemy.future import select
from sqlalchemy import func
from app.models import Zone
from app.models.zone import ZoneType
from app.schemas.schemas import ZoneCreate, ZoneUpdate
from app.core.h3_utils import lat_lng_to_h3_cell
from typing import Optional, List
import uuid


def create_zone(db: Session, owner_id: int, zone: ZoneCreate) -> Zone:
    """Create a new zone."""
    zone_id = str(uuid.uuid4())
    h3_cells = zone.h3_cells.copy()
    
    # If latitude and longitude provided, add the center cell
    if zone.latitude is not None and zone.longitude is not None:
        resolution = zone.h3_resolution or 13
        center_cell = lat_lng_to_h3_cell(zone.latitude, zone.longitude, resolution)
        if center_cell not in h3_cells:
            h3_cells.append(center_cell)
    
    db_zone = Zone(
        zone_id=zone_id,
        owner_id=owner_id,
        zone_type=ZoneType(zone.zone_type),
        name=zone.name,
        description=zone.description,
        h3_cells=h3_cells,
        parameters=zone.parameters or {},
    )
    db.add(db_zone)
    db.flush()
    db.refresh(db_zone)
    return db_zone


def get_zone(db: Session, zone_id: Optional[str] = None, owner_id: Optional[int] = None) -> Optional[Zone]:
    """Get a zone by zone_id and/or owner_id."""
    query = select(Zone)
    if zone_id is not None:
        query = query.where(Zone.zone_id == zone_id)
    if owner_id is not None:
        query = query.where(Zone.owner_id == owner_id)
    result = db.execute(query)
    return result.scalars().first()


def list_zones(
    db: Session,
    owner_id: int,
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
) -> List[Zone]:
    """List zones for an owner."""
    query = select(Zone).where(Zone.owner_id == owner_id)
    if active_only:
        query = query.where(Zone.active == True)
    query = query.offset(skip).limit(limit)
    result = db.execute(query)
    return result.scalars().all()


def update_zone(
    db: Session,
    zone_id: str,
    zone_update: ZoneUpdate,
    owner_id: Optional[int] = None,
) -> Optional[Zone]:
    """Update a zone."""
    db_zone = get_zone(db, zone_id, owner_id)
    if not db_zone:
        return None
    
    update_data = zone_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "zone_type" and value:
            value = ZoneType(value)
        setattr(db_zone, field, value)
    
    db.flush()
    db.refresh(db_zone)
    return db_zone


def delete_zone(db: Session, zone_id: str, owner_id: Optional[int] = None) -> bool:
    """Delete a zone."""
    db_zone = get_zone(db, zone_id, owner_id)
    if not db_zone:
        return False
    
    db.delete(db_zone)
    return True


def count_zones(db: Session, owner_id: int) -> int:
    """Count zones for an owner."""
    result = db.execute(
        select(func.count(Zone.id)).where(Zone.owner_id == owner_id)
    )
    return result.scalar()
