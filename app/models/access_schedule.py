"""Access schedule records used by permission flow."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String

from app.database import Base


class AccessSchedule(Base):
    __tablename__ = "access_schedules"

    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(String(100), nullable=False, index=True)
    event_id = Column(String(100), nullable=True, index=True)
    guest_id = Column(String(100), nullable=True, index=True)
    guest_name = Column(String(255), nullable=True, index=True)
    starts_at = Column(DateTime, nullable=True, index=True)
    ends_at = Column(DateTime, nullable=True, index=True)
    notify_member_assist = Column(Boolean, default=False, nullable=False)
    active = Column(Boolean, default=True, nullable=False, index=True)
    created_by_owner_id = Column(Integer, ForeignKey("owners.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_access_schedule_zone_event_guest", "zone_id", "event_id", "guest_id"),
    )
