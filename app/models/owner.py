"""Owner/User model."""
# UPDATED for Zoning-Messaging-System-Summary-v1.1.pdf
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Owner(Base):
    """Owner/User model."""
    __tablename__ = "owners"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    zone_id = Column(String(100), nullable=False, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    account_type = Column(String(32), nullable=False, default="private")
    hashed_password = Column(String(255), nullable=False)
    api_key = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20), nullable=True)
    address = Column(String(255), nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    expired = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    devices = relationship("Device", back_populates="owner", cascade="all, delete-orphan")
    zones = relationship("Zone", back_populates="owner", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="owner", cascade="all, delete-orphan")
    qr_registrations = relationship("QRRegistration", back_populates="owner", cascade="all, delete-orphan")
    sent_messages = relationship(
        "Message",
        foreign_keys="Message.sender_id",
        back_populates="sender",
        cascade="all, delete-orphan",
    )
    received_messages = relationship(
        "Message",
        foreign_keys="Message.receiver_id",
        back_populates="receiver",
    )

    __table_args__ = (
        Index("ix_owner_email", "email"),
        Index("ix_owner_zone_id", "zone_id"),
        Index("ix_owner_api_key", "api_key"),
    )

    def __repr__(self) -> str:
        return f"<Owner(id={self.id}, email={self.email}, account_type={self.account_type})>"
