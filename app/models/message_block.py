"""Message delivery block rules."""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String

from app.database import Base


class MessageBlock(Base):
    __tablename__ = "message_blocks"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, index=True)
    blocked_owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=True, index=True)
    blocked_message_type = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_message_block_owner_sender_type", "owner_id", "blocked_owner_id", "blocked_message_type"),
    )
