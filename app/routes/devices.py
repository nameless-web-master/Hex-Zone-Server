"""Device routes."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.crud import device as device_crud
from app.database import get_db
from app.schemas.schemas import DeviceCreate, DeviceLocationUpdate, DeviceUpdate
from app.utils.api_response import success_response

router = APIRouter(prefix="/devices", tags=["devices"])


def _serialize_device(device):
    return {
        "id": device.id,
        "hid": device.hid,
        "device_id": device.device_id,
        "name": device.name,
        "latitude": device.latitude,
        "longitude": device.longitude,
        "address": device.address,
        "h3_cell_id": device.h3_cell_id,
        "owner_id": device.owner_id,
        "propagate_enabled": device.propagate_enabled,
        "propagate_radius_km": device.propagate_radius_km,
        "active": device.active,
        "is_online": device.is_online,
        "last_seen": device.last_seen.isoformat() if device.last_seen else None,
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_device(payload: DeviceCreate, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    row = device_crud.create_device(db, current_user["user_id"], payload)
    db.commit()
    return success_response(_serialize_device(row), status_code=status.HTTP_201_CREATED)


@router.get("/")
async def list_devices(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = device_crud.list_devices(db, owner_id=current_user["user_id"], skip=skip, limit=limit)
    return success_response([_serialize_device(item) for item in rows])


@router.post("/{device_id}/location")
async def update_device_location(
    device_id: int,
    payload: DeviceLocationUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = device_crud.get_device(db, device_id, owner_id=current_user["user_id"])
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    updated = device_crud.update_device(
        db,
        device_id,
        DeviceUpdate(latitude=payload.latitude, longitude=payload.longitude, address=payload.address),
        owner_id=current_user["user_id"],
    )
    device_crud.touch_presence(db, updated)
    db.commit()
    return success_response(_serialize_device(updated))


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(device_id: int, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    deleted = device_crud.delete_device(db, device_id, owner_id=current_user["user_id"])
    if deleted:
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
