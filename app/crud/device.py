"""CRUD operations for Device."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from app.models import Device
from app.schemas.schemas import DeviceCreate, DeviceUpdate
from app.core.h3_utils import lat_lng_to_h3_cell
from typing import Optional, List


async def create_device(db: AsyncSession, owner_id: int, device: DeviceCreate) -> Device:
    """Create a new device."""
    h3_cell_id = None
    if device.latitude is not None and device.longitude is not None:
        h3_cell_id = lat_lng_to_h3_cell(device.latitude, device.longitude)
    
    db_device = Device(
        hid=device.hid,
        name=device.name,
        latitude=device.latitude,
        longitude=device.longitude,
        address=device.address,
        h3_cell_id=h3_cell_id,
        owner_id=owner_id,
        propagate_enabled=device.propagate_enabled,
        propagate_radius_km=device.propagate_radius_km,
    )
    db.add(db_device)
    await db.flush()
    await db.refresh(db_device)
    return db_device


async def get_device(db: AsyncSession, device_id: int, owner_id: Optional[int] = None) -> Optional[Device]:
    """Get a device by ID, optionally filtered by owner."""
    query = select(Device).where(Device.id == device_id)
    if owner_id is not None:
        query = query.where(Device.owner_id == owner_id)
    result = await db.execute(query)
    return result.scalars().first()


async def get_device_by_hid(db: AsyncSession, hid: str, owner_id: Optional[int] = None) -> Optional[Device]:
    """Get a device by hardware ID."""
    query = select(Device).where(Device.hid == hid)
    if owner_id is not None:
        query = query.where(Device.owner_id == owner_id)
    result = await db.execute(query)
    return result.scalars().first()


async def list_devices(
    db: AsyncSession,
    owner_id: int,
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
) -> List[Device]:
    """List devices for an owner."""
    query = select(Device).where(Device.owner_id == owner_id)
    if active_only:
        query = query.where(Device.active == True)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def update_device(
    db: AsyncSession,
    device_id: int,
    device_update: DeviceUpdate,
    owner_id: Optional[int] = None,
) -> Optional[Device]:
    """Update a device."""
    db_device = await get_device(db, device_id, owner_id)
    if not db_device:
        return None
    
    update_data = device_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_device, field, value)
    
    await db.flush()
    await db.refresh(db_device)
    return db_device


async def delete_device(db: AsyncSession, device_id: int, owner_id: Optional[int] = None) -> bool:
    """Delete a device."""
    db_device = await get_device(db, device_id, owner_id)
    if not db_device:
        return False
    
    await db.delete(db_device)
    return True


async def count_devices(db: AsyncSession, owner_id: int) -> int:
    """Count devices for an owner."""
    result = await db.execute(
        select(func.count(Device.id)).where(Device.owner_id == owner_id)
    )
    return result.scalar()
