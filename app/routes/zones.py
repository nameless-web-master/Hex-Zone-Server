"""Zone routes."""
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session
from app.controllers import zone_controller
from app.core.security import get_current_user
from app.crud import zone as zone_crud
from app.database import get_db
from app.schemas.schemas import ZoneCreate, ZoneUpdate
from app.utils.api_response import success_response

router = APIRouter(prefix="/zones", tags=["zones"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_zone(
    payload: ZoneCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    zone = zone_controller.create_zone(db, current_user["user_id"], payload)
    return success_response(zone_crud.zone_to_dict(zone), status_code=status.HTTP_201_CREATED)


@router.get("/")
async def list_zones(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    owner_id: int | None = Query(None, ge=1),
    zone_id: str | None = Query(None, min_length=1),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if zone_id is not None:
        zones = zone_crud.list_zones_by_zone_id_with_geojson(db, zone_id=zone_id, skip=skip, limit=limit)
    else:
        zones = zone_crud.list_zones_with_geojson(
            db,
            owner_id=owner_id or current_user["user_id"],
            skip=skip,
            limit=limit,
        )
    return success_response([zone_crud.zone_to_dict(zone) for zone in zones])


@router.patch("/{zone_id}")
async def update_zone(
    zone_id: str,
    payload: ZoneUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    zone = zone_controller.update_zone(db, current_user["user_id"], zone_id, payload)
    return success_response(zone_crud.zone_to_dict(zone))


@router.delete("/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_zone(zone_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    deleted = zone_crud.delete_zone(db, zone_id, owner_id=current_user["user_id"])
    if deleted:
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
