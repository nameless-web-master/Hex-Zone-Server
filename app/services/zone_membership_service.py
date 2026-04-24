"""Services for maintaining dynamic zone memberships."""
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Owner, ZoneMembership
from app.services.access_policy import visible_owner_ids
from app.services.geospatial_service import evaluate_member_zones


def refresh_owner_memberships(db: Session, owner: Owner, latitude: float, longitude: float) -> list[str]:
    candidate_owner_ids = visible_owner_ids(db, owner, include_inactive=False)
    matched_zone_ids = evaluate_member_zones(db, latitude, longitude, candidate_owner_ids)

    db.query(ZoneMembership).filter(ZoneMembership.owner_id == owner.id).delete()
    for zone_id in matched_zone_ids:
        db.add(
            ZoneMembership(
                owner_id=owner.id,
                zone_id=zone_id,
                updated_at=datetime.utcnow(),
            )
        )
    db.flush()
    return matched_zone_ids
