"""Member location snapshot model."""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer
from sqlalchemy.orm import relationship

from app.database import Base


class MemberLocation(Base):
    __tablename__ = "member_locations"

    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), primary_key=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    owner = relationship("Owner")

    __table_args__ = (
        Index("ix_member_locations_updated_at", "updated_at"),
    )
