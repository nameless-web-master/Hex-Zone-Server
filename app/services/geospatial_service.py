"""Geospatial evaluation service."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models import MemberLocation, Zone


def evaluate_owner_zone_membership(db: Session, owner_id: int) -> list[str]:
    """Return zone_ids where owner point is inside zone geometry or H3 cells."""
    location = db.execute(select(MemberLocation).where(MemberLocation.owner_id == owner_id)).scalars().first()
    if not location:
        return []

    geom_matches = db.execute(
        select(Zone.zone_id)
        .where(Zone.active.is_(True))
        .where(Zone.geo_fence_polygon.is_not(None))
        .where(func.ST_Contains(Zone.geo_fence_polygon, location.point))
    ).scalars().all()

    h3_zone_rows = db.execute(
        select(Zone.zone_id, Zone.h3_cells).where(Zone.active.is_(True)).where(Zone.h3_cells.is_not(None))
    ).all()
    h3_matches = [zone_id for zone_id, h3_cells in h3_zone_rows if location.h3_cell_id and location.h3_cell_id in (h3_cells or [])]

    return sorted(set(geom_matches + h3_matches))
