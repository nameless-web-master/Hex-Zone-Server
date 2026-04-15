"""Device management service for push tokens."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import DeviceToken


def upsert_push_token(db: Session, owner_id: int, token: str, platform: str) -> dict:
    """Store or reactivate push token."""
    existing = db.execute(select(DeviceToken).where(DeviceToken.token == token)).scalars().first()
    if existing:
        existing.owner_id = owner_id
        existing.platform = platform
        existing.active = True
        db.commit()
        return {"id": existing.id, "token": existing.token, "platform": existing.platform, "active": existing.active}

    row = DeviceToken(owner_id=owner_id, token=token, platform=platform, active=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "token": row.token, "platform": row.platform, "active": row.active}
