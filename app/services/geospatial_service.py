"""Geospatial evaluation using H3 and PostGIS-compatible data."""
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.h3_utils import lat_lng_to_h3_cell
from app.models import Zone


def evaluate_member_zones(db: Session, latitude: float, longitude: float, candidate_owner_ids: Iterable[int]) -> list[str]:
    owner_ids = list(candidate_owner_ids)
    if not owner_ids:
        return []

    h3_cell = lat_lng_to_h3_cell(latitude, longitude, 13)
    h3_matches = (
        db.query(Zone.zone_id)
        .filter(Zone.owner_id.in_(owner_ids), Zone.active.is_(True), Zone.h3_cells.contains([h3_cell]))
        .all()
    )
    matched = {row[0] for row in h3_matches}

    postgis_sql = text(
        """
        SELECT z.zone_id
        FROM zones z
        WHERE z.owner_id = ANY(:owner_ids)
          AND z.active = TRUE
          AND z.geo_fence_polygon IS NOT NULL
          AND ST_Contains(
              z.geo_fence_polygon,
              ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)
          )
        """
    )
    for row in db.execute(postgis_sql, {"owner_ids": owner_ids, "longitude": longitude, "latitude": latitude}):
        matched.add(row[0])

    return sorted(matched)
