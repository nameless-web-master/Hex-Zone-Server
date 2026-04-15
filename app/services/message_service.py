"""Zone messaging service."""
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from sqlalchemy import delete
from sqlalchemy.orm import Session
from app.crud import message as message_crud
from app.crud import owner as owner_crud
from app.models import Message
from app.schemas.schemas import MessageVisibilityEnum, ZoneMessageCreate


def create_message(db: Session, owner_id: int, payload: ZoneMessageCreate):
    """Create zone-scoped message with visibility checks."""
    sender = owner_crud.get_owner(db, owner_id)
    if not sender:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sender owner not found")

    if payload.visibility == MessageVisibilityEnum.PRIVATE and payload.receiver_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="receiver_id is required")
    if payload.visibility == MessageVisibilityEnum.PUBLIC and payload.receiver_id is not None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="receiver_id must be omitted")

    if payload.receiver_id:
        receiver = owner_crud.get_owner(db, payload.receiver_id)
        if not receiver or receiver.zone_id != sender.zone_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Receiver is not in sender zone")

    prune_before = datetime.utcnow() - timedelta(days=30)
    db.execute(delete(Message).where(Message.created_at < prune_before))

    msg = message_crud.create_message(db, sender_id=sender.id, payload=payload)
    db.commit()
    return msg, sender.zone_id
