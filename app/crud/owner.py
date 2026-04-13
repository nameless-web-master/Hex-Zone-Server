"""CRUD operations for Owner/User."""
import json
from sqlalchemy.orm import Session
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func
from app.models import Owner, Zone
from app.schemas.schemas import OwnerCreate, OwnerUpdate
from app.core.security import get_password_hash, generate_api_key
from typing import Optional


def create_owner(db: Session, owner: OwnerCreate) -> Owner:
    """Create a new owner."""
    api_key = generate_api_key()
    db_owner = Owner(
        email=owner.email,
        first_name=owner.first_name,
        last_name=owner.last_name,
        account_type=owner.account_type,
        hashed_password=get_password_hash(owner.password),
        api_key=api_key,
        phone=owner.phone,
        address=owner.address,
    )
    db.add(db_owner)
    db.flush()
    db.refresh(db_owner)
    return db_owner


def _geojson_text_to_dict(geojson_text: Optional[str]) -> Optional[dict]:
    if geojson_text is None:
        return None
    return json.loads(geojson_text)


def get_owner(db: Session, owner_id: int) -> Optional[Owner]:
    """Get an owner by ID."""
    result = db.execute(
        select(Owner)
        .where(Owner.id == owner_id)
        .options(selectinload(Owner.devices), selectinload(Owner.zones))
    )
    owner = result.scalars().first()

    if owner and owner.zones:
        zone_ids = [zone.id for zone in owner.zones if zone.geo_fence_polygon is not None]
        if zone_ids:
            geojson_rows = db.execute(
                select(Zone.id, func.ST_AsGeoJSON(Zone.geo_fence_polygon))
                .where(Zone.id.in_(zone_ids))
            ).all()
            geojson_map = {zone_id: _geojson_text_to_dict(geojson_text) for zone_id, geojson_text in geojson_rows}
            for zone in owner.zones:
                if zone.id in geojson_map:
                    zone.geo_fence_polygon = geojson_map[zone.id]

    return owner


def get_owner_by_email(db: Session, email: str) -> Optional[Owner]:
    """Get an owner by email."""
    result = db.execute(select(Owner).where(Owner.email == email))
    return result.scalars().first()


def get_owner_by_api_key(db: Session, api_key: str) -> Optional[Owner]:
    """Get an owner by API key."""
    result = db.execute(select(Owner).where(Owner.api_key == api_key))
    return result.scalars().first()


def list_owners(db: Session, skip: int = 0, limit: int = 100):
    """List all owners."""
    result = db.execute(
        select(Owner)
        .offset(skip)
        .limit(limit)
        .options(selectinload(Owner.devices), selectinload(Owner.zones))
    )
    return result.scalars().all()


def update_owner(db: Session, owner_id: int, owner_update: OwnerUpdate) -> Optional[Owner]:
    """Update an owner."""
    db_owner = get_owner(db, owner_id)
    if not db_owner:
        return None
    
    update_data = owner_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_owner, field, value)
    
    db.flush()
    db.refresh(db_owner)
    return db_owner


def delete_owner(db: Session, owner_id: int) -> bool:
    """Delete an owner."""
    db_owner = get_owner(db, owner_id)
    if not db_owner:
        return False
    
    db.delete(db_owner)
    return True


def count_owners(db: Session) -> int:
    """Count all owners."""
    result = db.execute(select(Owner))
    return len(result.scalars().all())
