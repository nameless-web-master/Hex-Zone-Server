"""Server-issued registration codes for administrator self-service signup."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String

from app.database import Base


class RegistrationCode(Base):
    """Single-use registration token (similar lifecycle to QR invite codes)."""

    __tablename__ = "registration_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(255), unique=True, nullable=False, index=True)
    used = Column(Boolean, default=False, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_registration_codes_code", "code"),
        Index("ix_registration_codes_expires_at", "expires_at"),
    )

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    def __repr__(self) -> str:
        return f"<RegistrationCode(id={self.id}, used={self.used}, revoked={self.revoked})>"
