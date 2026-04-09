"""CRUD operations for QR Registration."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models import QRRegistration
from app.core.security import generate_qr_token
from datetime import datetime, timedelta
from typing import Optional


async def create_qr_registration(
    db: AsyncSession,
    owner_id: int,
    expires_in_hours: int = 24,
) -> QRRegistration:
    """Create a new QR registration token."""
    token = generate_qr_token()
    expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
    
    db_qr = QRRegistration(
        token=token,
        owner_id=owner_id,
        expires_at=expires_at,
    )
    db.add(db_qr)
    await db.flush()
    await db.refresh(db_qr)
    return db_qr


async def get_qr_registration(db: AsyncSession, token: str) -> Optional[QRRegistration]:
    """Get a QR registration by token."""
    result = await db.execute(
        select(QRRegistration).where(QRRegistration.token == token)
    )
    return result.scalars().first()


async def mark_qr_registration_used(db: AsyncSession, token: str) -> Optional[QRRegistration]:
    """Mark a QR registration as used."""
    qr = await get_qr_registration(db, token)
    if not qr:
        return None
    
    qr.used = True
    await db.flush()
    await db.refresh(qr)
    return qr


async def list_qr_registrations(
    db: AsyncSession,
    owner_id: int,
    skip: int = 0,
    limit: int = 100,
) -> list:
    """List QR registrations for an owner."""
    result = await db.execute(
        select(QRRegistration)
        .where(QRRegistration.owner_id == owner_id)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()
