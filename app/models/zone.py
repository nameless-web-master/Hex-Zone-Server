"""Zone model."""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Index, JSON, Text, Enum, Boolean
from sqlalchemy.orm import relationship, validates
from geoalchemy2 import Geometry
from datetime import datetime
import enum
from app.database import Base


def _polygon_coords_to_wkt(polygon_coords: list[list[list[float]]]) -> str:
    rings = []
    for ring in polygon_coords:
        rings.append("(" + ", ".join(f"{lng} {lat}" for lng, lat in ring) + ")")
    return "(" + ",".join(rings) + ")"


def geojson_to_wkt(geojson: dict) -> str:
    geometry_type = geojson.get("type")
    if geometry_type not in ("Polygon", "MultiPolygon"):
        raise ValueError("geo_fence_polygon must be a GeoJSON Polygon or MultiPolygon")

    if geometry_type == "Polygon":
        polygon_text = _polygon_coords_to_wkt(geojson["coordinates"])
        return f"MULTIPOLYGON({polygon_text})"

    multipolygon_text = ",".join(_polygon_coords_to_wkt(polygon) for polygon in geojson["coordinates"])
    return f"MULTIPOLYGON({multipolygon_text})"


class ZoneType(str, enum.Enum):
    """Zone type enumeration."""
    WARN = "warn"
    ALERT = "alert"
    GEOFENCE = "geofence"
    EMERGENCY = "emergency"
    RESTRICTED = "restricted"
    CUSTOM_1 = "custom_1"
    CUSTOM_2 = "custom_2"


class Zone(Base):
    """Zone model."""
    __tablename__ = "zones"

    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(String(36), nullable=False, index=True)  # UUID or custom ID (shared across owners)
    
    # Owner reference
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, index=True)
    creator_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Zone configuration
    zone_type = Column(Enum(ZoneType), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # H3 cells for this zone
    h3_cells = Column(JSON, nullable=False, default=list)  # Array of H3 cell IDs
    
    # PostGIS geometry for polygon-based zones
    geo_fence_polygon = Column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)
    
    # Zone parameters (flexible JSON for different zone types)
    parameters = Column(JSON, nullable=True)
    
    # Status
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    owner = relationship("Owner", back_populates="zones", foreign_keys=[owner_id])
    creator = relationship("Owner", foreign_keys=[creator_id], back_populates="created_zones")

    @validates("geo_fence_polygon")
    def validate_geo_fence_polygon(self, key, value):
        if value is None:
            return None
        if isinstance(value, dict):
            return f"SRID=4326;{geojson_to_wkt(value)}"
        return value

    __table_args__ = (
        Index("ix_zone_zone_id", "zone_id"),
        Index("ix_zone_owner_id", "owner_id"),
        Index("ix_zone_creator_id", "creator_id"),
    )

    def __repr__(self) -> str:
        return f"<Zone(id={self.id}, zone_id={self.zone_id}, zone_type={self.zone_type})>"
