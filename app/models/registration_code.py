"""Server-issued registration codes for administrator self-service signup."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.database import Base


class RegistrationCode(Base):
    """Single-use registration token (similar lifecycle to QR invite codes)."""

    __tablename__ = "registration_codes"

    id = Column(Integer, primary_key=True)
    # unique=True creates the unique index/constraint. Do not also set index=True or add
    # Index("ix_registration_codes_code", ...) — that duplicates the same ix_* name and
    # makes PostgreSQL raise "relation ... already exists" during create_all().
    code = Column(String(255), unique=True, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    def __repr__(self) -> str:
        return f"<RegistrationCode(id={self.id}, used={self.used}, revoked={self.revoked})>"
