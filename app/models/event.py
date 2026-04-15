"""Schedule access event model."""
# UPDATED for Zoning-Messaging-System-Summary-v1.1.pdf
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Date, Time, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database import Base


class Event(Base):
    """Basic event model used by /events CRUD endpoints."""

    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    event_id = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)

    zone_id = Column(String(100), ForeignKey("zones.zone_id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    owner = relationship("Owner", back_populates="events")
    zone = relationship("Zone", back_populates="events")

    __table_args__ = (
        Index("ix_event_owner_zone", "owner_id", "zone_id"),
    )

    def __repr__(self) -> str:
        return f"<Event(id={self.id}, event_id={self.event_id}, owner_id={self.owner_id})>"
