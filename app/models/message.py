"""Zone message model."""
# UPDATED for Zoning-Messaging-System-Summary-v1.1.pdf
from datetime import datetime
from sqlalchemy import Column, Integer, Text, DateTime, String, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database import Base


class Message(Base):
    """Zone message model."""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, index=True)
    receiver_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=True, index=True)
    message_type = Column(String(32), nullable=False, index=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    sender = relationship("Owner", foreign_keys=[sender_id], back_populates="sent_messages")
    receiver = relationship("Owner", foreign_keys=[receiver_id], back_populates="received_messages")

    __table_args__ = (
        Index("ix_message_sender_receiver", "sender_id", "receiver_id"),
        Index("ix_message_type_created", "message_type", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Message(id={self.id}, sender_id={self.sender_id}, "
            f"receiver_id={self.receiver_id}, message_type={self.message_type})>"
        )
