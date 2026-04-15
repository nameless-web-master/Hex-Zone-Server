"""Member location model."""
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from geoalchemy2 import Geometry
from app.database import Base


class MemberLocation(Base):
    """Stores latest owner/member location for geospatial evaluation."""

    __tablename__ = "member_locations"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    point = Column(Geometry("POINT", srid=4326), nullable=False)
    h3_cell_id = Column(String(50), nullable=True, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_member_locations_owner", "owner_id"),
        Index("ix_member_locations_h3_cell", "h3_cell_id"),
    )
