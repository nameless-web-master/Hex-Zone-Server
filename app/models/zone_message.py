"""Zone message model (public broadcast or private between two owners)."""
import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Index, Text
from sqlalchemy.orm import relationship

from app.database import Base


class MessageVisibility(str, enum.Enum):
    """Who can read the message."""

    PUBLIC = "public"
    PRIVATE = "private"


class ZoneMessage(Base):
    """A message posted in a zone."""

    __tablename__ = "zone_messages"

    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(Integer, ForeignKey("zones.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, index=True)
    receiver_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=True, index=True)
    visibility = Column(
        Enum(MessageVisibility, native_enum=False, length=20),
        nullable=False,
    )
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    zone = relationship("Zone", back_populates="messages")
    sender = relationship("Owner", foreign_keys=[sender_id])
    receiver = relationship("Owner", foreign_keys=[receiver_id])

    __table_args__ = (
        Index("ix_zone_messages_zone_created", "zone_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ZoneMessage(id={self.id}, zone_id={self.zone_id}, visibility={self.visibility})>"
