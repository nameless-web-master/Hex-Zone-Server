"""Contract message services and retention logic."""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.domain.message_types import normalize_message_type, type_category, type_scope
from app.models.zone_message_event import ZoneMessageEvent


def create_zone_message(db: Session, sender_id: int, payload: dict) -> dict:
    try:
        msg_type = normalize_message_type(payload["type"])
    except (KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_code": "INVALID_MESSAGE_TYPE", "message": "Unsupported message type."},
        )

    message = ZoneMessageEvent(
        zone_id=payload["zoneId"],
        sender_id=sender_id,
        type=msg_type.value,
        category=type_category(msg_type),
        scope=type_scope(msg_type),
        text=payload["text"],
        body_json={"text": payload["text"]},
        metadata_json=payload.get("metadata", {}),
    )
    db.add(message)
    db.flush()
    db.refresh(message)
    return {
        "id": message.id,
        "zoneId": message.zone_id,
        "text": message.text,
        "type": message.type,
        "category": message.category.value,
        "scope": message.scope.value,
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
            "type": row.type,
            "category": row.category.value,
            "scope": row.scope.value,
            "createdAt": row.created_at.isoformat(),
        }
        for row in rows
    ]
