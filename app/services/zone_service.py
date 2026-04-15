"""Zone services with contract type mappings and constraints."""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Owner, Zone
from app.models.zone import ZoneType

CONTRACT_TO_MODEL_ZONE_TYPE = {
    "polygon": ZoneType.GEOFENCE,
    "geofence": ZoneType.GEOFENCE,
    "circle": ZoneType.WARN,
    "warn": ZoneType.WARN,
    "grid": ZoneType.ALERT,
    "alert": ZoneType.ALERT,
    "dynamic": ZoneType.CUSTOM_1,
    "custom_1": ZoneType.CUSTOM_1,
    "proximity": ZoneType.RESTRICTED,
    "restricted": ZoneType.RESTRICTED,
    "object": ZoneType.CUSTOM_2,
    "custom_2": ZoneType.CUSTOM_2,
}

MODEL_TO_CONTRACT_ZONE_TYPE = {value: key for key, value in CONTRACT_TO_MODEL_ZONE_TYPE.items()}


def _extract_geojson_polygon(geometry: object) -> dict | None:
    """Return GeoJSON Polygon/MultiPolygon dict, otherwise None."""
    if not isinstance(geometry, dict):
        return None
    geometry_type = geometry.get("type")
    if geometry_type in {"Polygon", "MultiPolygon"}:
        return geometry
    return None


def _serialize_zone(zone: Zone) -> dict:
    contract_type = (zone.parameters or {}).get("contractType")
    return {
        "id": zone.zone_id,
        "name": zone.name,
        "type": contract_type or MODEL_TO_CONTRACT_ZONE_TYPE.get(zone.zone_type, "dynamic"),
        "geometry": (zone.parameters or {}).get("geometry", {}),
        "config": (zone.parameters or {}).get("config", {}),
    }


def create_zone(db: Session, owner: Owner, payload: dict) -> dict:
    count = db.query(Zone).filter(Zone.owner_id == owner.id).count()
    if count >= 3:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Maximum 3 zones per user")

    zone_type = payload["type"]
    if zone_type not in CONTRACT_TO_MODEL_ZONE_TYPE:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported zone type")

    geometry = payload.get("geometry", {})
    geo_fence_polygon = _extract_geojson_polygon(geometry)

    zone = Zone(
        zone_id=payload.get("id") or f"{owner.id}-{count + 1}",
        owner_id=owner.id,
        zone_type=CONTRACT_TO_MODEL_ZONE_TYPE[zone_type],
        name=payload["name"],
        parameters={
            "contractType": zone_type,
            "geometry": geometry,
            "config": payload.get("config", {}),
        },
        h3_cells=payload.get("config", {}).get("h3Cells", []),
        geo_fence_polygon=geo_fence_polygon,
    )
    db.add(zone)
    db.flush()
    db.refresh(zone)
    return _serialize_zone(zone)


def list_zones(db: Session, owner: Owner) -> list[dict]:
    zones = db.query(Zone).filter(Zone.owner_id == owner.id, Zone.active.is_(True)).all()
    return [_serialize_zone(zone) for zone in zones]


def update_zone(db: Session, owner: Owner, zone_id: str, payload: dict) -> dict:
    zone = db.query(Zone).filter(Zone.owner_id == owner.id, Zone.zone_id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found")
    if payload.get("name"):
        zone.name = payload["name"]
    if payload.get("type"):
        zone_type = payload["type"]
        if zone_type not in CONTRACT_TO_MODEL_ZONE_TYPE:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported zone type")
        zone.zone_type = CONTRACT_TO_MODEL_ZONE_TYPE[zone_type]
    params = zone.parameters or {}
    if "geometry" in payload:
        geometry = payload.get("geometry", {})
        params["geometry"] = geometry
        zone.geo_fence_polygon = _extract_geojson_polygon(geometry)
    if "config" in payload:
        params["config"] = payload.get("config", {})
    if payload.get("type"):
        params["contractType"] = payload["type"]
    zone.parameters = params
    db.flush()
    return _serialize_zone(zone)


def delete_zone(db: Session, owner: Owner, zone_id: str) -> None:
    zone = db.query(Zone).filter(Zone.owner_id == owner.id, Zone.zone_id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found")
    db.delete(zone)
