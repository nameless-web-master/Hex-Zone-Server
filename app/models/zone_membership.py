"""Continuously refreshed owner-to-zone membership snapshots."""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String

from app.database import Base


class ZoneMembership(Base):
    __tablename__ = "zone_memberships"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, index=True)
    zone_id = Column(String(100), nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("ix_zone_membership_owner_zone", "owner_id", "zone_id"),
    )
