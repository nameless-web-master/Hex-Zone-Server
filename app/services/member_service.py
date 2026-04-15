"""Member service."""
from datetime import datetime
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.h3_utils import lat_lng_to_h3_cell
from app.crud import owner as owner_crud, zone as zone_crud
from app.models import MemberLocation
from app.services.geospatial_service import evaluate_owner_zone_membership


def update_member_location(db: Session, owner_id: int, latitude: float, longitude: float):
    """Store member location and return matching zones."""
    location = db.execute(select(MemberLocation).where(MemberLocation.owner_id == owner_id)).scalars().first()
    h3_cell = lat_lng_to_h3_cell(latitude, longitude)
    ewkt = f"SRID=4326;POINT({longitude} {latitude})"
    if location is None:
        location = MemberLocation(owner_id=owner_id, point=ewkt, h3_cell_id=h3_cell)
        db.add(location)
    else:
        location.point = ewkt
        location.h3_cell_id = h3_cell
        location.updated_at = datetime.utcnow()
    db.flush()
    memberships = evaluate_owner_zone_membership(db, owner_id)
    db.commit()
    return {"owner_id": owner_id, "latitude": latitude, "longitude": longitude, "matched_zones": memberships}


def list_members(db: Session):
    """List members with latest location and zones."""
    owners = owner_crud.list_owners(db, skip=0, limit=1000)
    location_rows = db.execute(
        select(
            MemberLocation.owner_id,
            MemberLocation.updated_at,
            func.ST_Y(MemberLocation.point).label("latitude"),
            func.ST_X(MemberLocation.point).label("longitude"),
        )
    ).all()
    locations = {row.owner_id: row for row in location_rows}
    members = []
    for owner in owners:
        loc = locations.get(owner.id)
        lat = lon = None
        if loc:
            lat = loc.latitude
            lon = loc.longitude
        zones = zone_crud.list_zones_with_geojson(db, owner_id=owner.id, skip=0, limit=50)
        members.append(
            {
                "id": owner.id,
                "name": f"{owner.first_name} {owner.last_name}".strip(),
                "location": {"latitude": lat, "longitude": lon} if lat is not None and lon is not None else None,
                "lastSeen": loc.updated_at.isoformat() if loc and loc.updated_at else None,
                "zones": [zone.zone_id for zone in zones],
            }
        )
    return members
