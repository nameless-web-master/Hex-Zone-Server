"""Contract message services and retention logic."""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.zone_message_event import ContractMessageType, ZoneMessageEvent


def create_zone_message(db: Session, sender_id: int, payload: dict) -> dict:
    msg_type = payload["type"]
    if msg_type not in {item.value for item in ContractMessageType}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid message type")

    message = ZoneMessageEvent(
        zone_id=payload["zoneId"],
        sender_id=sender_id,
        type=ContractMessageType(msg_type),
        text=payload["text"],
        metadata_json=payload.get("metadata", {}),
    )
    db.add(message)
    db.flush()
    db.refresh(message)
    return {
        "id": message.id,
        "zoneId": message.zone_id,
        "text": message.text,
        "type": message.type.value,
        "createdAt": message.created_at.isoformat(),
    }


def list_new_messages(db: Session, since_iso: str) -> list[dict]:
    since = datetime.fromisoformat(since_iso.replace("Z", "+00:00"))
    if since.tzinfo is not None:
        since = since.astimezone(timezone.utc).replace(tzinfo=None)
    retention_cutoff = datetime.utcnow() - timedelta(days=30)
    since = max(since, retention_cutoff)
    rows = (
        db.query(ZoneMessageEvent)
        .filter(ZoneMessageEvent.created_at >= since)
        .order_by(ZoneMessageEvent.created_at.asc())
        .limit(500)
        .all()
    )
    return [
        {
            "id": row.id,
            "zoneId": row.zone_id,
            "text": row.text,
            "type": row.type.value,
            "createdAt": row.created_at.isoformat(),
        }
        for row in rows
    ]
