"""Zone message model."""
from datetime import datetime
import enum
from sqlalchemy import Column, Integer, Text, DateTime, Enum, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database import Base


class MessageVisibility(str, enum.Enum):
    """Message visibility enumeration."""

    PUBLIC = "public"
    PRIVATE = "private"


class MessageType(str, enum.Enum):
    """Message type classification."""

    NORMAL = "NORMAL"
    PANIC = "PANIC"
    NS_PANIC = "NS_PANIC"
    SENSOR = "SENSOR"


class Message(Base):
    """Zone message model."""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, index=True)
    receiver_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=True, index=True)
    visibility = Column(Enum(MessageVisibility), nullable=False)
    message_type = Column(Enum(MessageType), nullable=False, default=MessageType.NORMAL)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    sender = relationship("Owner", foreign_keys=[sender_id], back_populates="sent_messages")
    receiver = relationship("Owner", foreign_keys=[receiver_id], back_populates="received_messages")

    __table_args__ = (
        Index("ix_message_sender_receiver", "sender_id", "receiver_id"),
        Index("ix_message_visibility_created", "visibility", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Message(id={self.id}, sender_id={self.sender_id}, "
            f"receiver_id={self.receiver_id}, visibility={self.visibility})>"
        )
