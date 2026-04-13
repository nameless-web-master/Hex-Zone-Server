"""Zone model."""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Index, JSON, Text, Enum, Boolean
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from datetime import datetime
import enum
from app.database import Base


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
    zone_id = Column(String(36), unique=True, nullable=False, index=True)  # UUID or custom ID
    
    # Owner reference
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, index=True)
    
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
    owner = relationship("Owner", back_populates="zones")

    __table_args__ = (
        Index("ix_zone_zone_id", "zone_id"),
        Index("ix_zone_owner_id", "owner_id"),
    )

    def __repr__(self) -> str:
        return f"<Zone(id={self.id}, zone_id={self.zone_id}, zone_type={self.zone_type})>"
