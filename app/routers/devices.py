"""Router for Device endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.schemas import (
    DeviceCreate,
    DeviceResponse,
    DeviceUpdate,
    DeviceLocationUpdate,
)
from app.crud import device as device_crud
from app.crud import owner as owner_crud
from app.core.security import get_current_user
from app.core.h3_utils import lat_lng_to_h3_cell
from typing import Optional

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("/", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def create_device(
    device: DeviceCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new device for the current owner."""
    db_device = await device_crud.create_device(db, current_user["user_id"], device)
    await db.commit()
    return DeviceResponse.model_validate(db_device)


@router.get("/", response_model=list[DeviceResponse])
async def list_devices(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List devices for the current owner."""
    devices = await device_crud.list_devices(
        db,
        owner_id=current_user["user_id"],
        skip=skip,
        limit=limit,
    )
    return [DeviceResponse.model_validate(device) for device in devices]


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a device by ID."""
    device = await device_crud.get_device(db, device_id, owner_id=current_user["user_id"])
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    return DeviceResponse.model_validate(device)


@router.get("/network/hid/{hid}", response_model=DeviceResponse)
async def get_device_by_hid(
    hid: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a device by hardware ID."""
    device = await device_crud.get_device_by_hid(db, hid, owner_id=current_user["user_id"])
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    return DeviceResponse.model_validate(device)


@router.patch("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: int,
    device_update: DeviceUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a device."""
    device = await device_crud.update_device(
        db,
        device_id,
        device_update,
        owner_id=current_user["user_id"],
    )
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    await db.commit()
    return DeviceResponse.model_validate(device)


@router.post("/{device_id}/location", response_model=DeviceResponse)
async def update_device_location(
    device_id: int,
    location: DeviceLocationUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update device location and calculate H3 cell."""
    device = await device_crud.get_device(db, device_id, owner_id=current_user["user_id"])
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    
    # Calculate H3 cell
    h3_cell_id = lat_lng_to_h3_cell(location.latitude, location.longitude)
    
    # Update device
    update_data = DeviceUpdate(
        latitude=location.latitude,
        longitude=location.longitude,
        address=location.address,
    )
    updated_device = await device_crud.update_device(
        db,
        device_id,
        update_data,
        owner_id=current_user["user_id"],
    )
    updated_device.h3_cell_id = h3_cell_id
    
    await db.commit()
    return DeviceResponse.model_validate(updated_device)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a device."""
    deleted = await device_crud.delete_device(db, device_id, owner_id=current_user["user_id"])
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    await db.commit()
