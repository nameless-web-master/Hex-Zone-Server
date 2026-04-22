"""CRUD for public registration codes."""
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.security import generate_registration_code_token
from app.models import RegistrationCode


def create_registration_code(db: Session, *, expires_in_hours: int) -> RegistrationCode:
    """Persist a new single-use registration code."""
    token = generate_registration_code_token()
    expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
    row = RegistrationCode(code=token, expires_at=expires_at)
    db.add(row)
    db.flush()
    db.refresh(row)
    return row


def get_registration_code(db: Session, code: str) -> RegistrationCode | None:
    return db.execute(select(RegistrationCode).where(RegistrationCode.code == code)).scalars().first()


def try_consume_registration_code(db: Session, code: str) -> bool:
    """Atomically mark a valid code as used. Returns True if one row was updated."""
    now = datetime.utcnow()
    result = db.execute(
        update(RegistrationCode)
        .where(
            RegistrationCode.code == code,
            RegistrationCode.used.is_(False),
            RegistrationCode.revoked.is_(False),
            RegistrationCode.expires_at > now,
        )
        .values(used=True)
    )
    return result.rowcount == 1
