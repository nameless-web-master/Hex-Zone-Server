"""Member listing and location tracking services."""
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import MemberLocation, Owner, PushToken, Zone
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


def list_members(db: Session, owner: Owner) -> list[dict]:
    members = db.query(Owner).filter(Owner.zone_id == owner.zone_id, Owner.active.is_(True)).all()
    output: list[dict] = []
    for member in members:
        location = db.get(MemberLocation, member.id)
        zones = db.query(Zone.zone_id).filter(Zone.owner_id == member.id, Zone.active.is_(True)).all()
        output.append(
            {
                "id": str(member.id),
                "name": member.first_name,
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
