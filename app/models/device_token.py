"""Device token model for push notifications."""
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String
from app.database import Base


class DeviceToken(Base):
    """Stores push device tokens for future FCM/APNs delivery."""

    __tablename__ = "device_tokens"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(512), nullable=False, unique=True)
    platform = Column(String(20), nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_device_tokens_owner", "owner_id"),
        Index("ix_device_tokens_token", "token"),
    )
