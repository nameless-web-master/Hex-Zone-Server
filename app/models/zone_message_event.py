"""Contract-oriented zone message history."""
import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Enum, ForeignKey, Index, String, Text

from app.database import Base


class ContractMessageType(str, enum.Enum):
    NORMAL = "NORMAL"
    PANIC = "PANIC"
    NS_PANIC = "NS_PANIC"
    SENSOR = "SENSOR"


class ZoneMessageEvent(Base):
    __tablename__ = "zone_message_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    zone_id = Column(String(100), nullable=False, index=True)
    sender_id = Column(ForeignKey("owners.id", ondelete="SET NULL"), nullable=True, index=True)
    type = Column(Enum(ContractMessageType), nullable=False, index=True)
    text = Column(Text, nullable=False)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("ix_zone_message_events_zone_created", "zone_id", "created_at"),
    )
