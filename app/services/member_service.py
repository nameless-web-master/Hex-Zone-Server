"""Member listing and location tracking services."""
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Device, MemberLocation, Owner, PushToken, Zone
from app.services.access_policy import visible_owner_ids
from app.services.geospatial_service import evaluate_member_zones


def upsert_member_location(db: Session, owner_id: int, latitude: float, longitude: float) -> dict:
    row = db.get(MemberLocation, owner_id)
    if row is None:
        row = MemberLocation(owner_id=owner_id, latitude=latitude, longitude=longitude)
        db.add(row)
    else:
        row.latitude = latitude
        row.longitude = longitude
        row.updated_at = datetime.utcnow()
    db.flush()
    zone_ids = evaluate_member_zones(db, latitude, longitude, [owner_id])
    return {"latitude": row.latitude, "longitude": row.longitude, "zones": zone_ids}


def list_members(db: Session, owner: Owner, active: bool | None = None) -> list[dict]:
    owner_ids = visible_owner_ids(db, owner)
    query = db.query(Owner).filter(Owner.id.in_(owner_ids))
    if active is not None:
        query = query.filter(Owner.active.is_(active))
    members = query.all()
    output: list[dict] = []
    for member in members:
        location = db.get(MemberLocation, member.id)
        if location is None:
            location = (
                db.query(Device)
                .filter(
                    Device.owner_id == member.id,
                    Device.latitude.isnot(None),
                    Device.longitude.isnot(None),
                )
                .order_by(Device.updated_at.desc())
                .first()
            )
        zones = db.query(Zone.zone_id).filter(Zone.owner_id == member.id, Zone.active.is_(True)).all()
        output.append(
            {
                "id": str(member.id),
                "name": f"{member.first_name} {member.last_name}".strip(),
                "first_name": member.first_name,
                "last_name": member.last_name,
                "address": member.address,
                "zone_id": member.zone_id,
                "active": member.active,
                "location": None
                if not location
                else {"latitude": location.latitude, "longitude": location.longitude},
                "lastSeen": None if not location else location.updated_at.isoformat(),
                "zones": [row[0] for row in zones],
            }
        )
    return output


def upsert_push_token(db: Session, owner_id: int, token: str, platform: str) -> dict:
    row = db.query(PushToken).filter(PushToken.token == token).first()
    if row is None:
        row = PushToken(owner_id=owner_id, token=token, platform=platform.upper(), active=True)
        db.add(row)
    else:
        row.owner_id = owner_id
        row.platform = platform.upper()
        row.active = True
    db.flush()
    return {"token": row.token, "platform": row.platform, "active": row.active}
