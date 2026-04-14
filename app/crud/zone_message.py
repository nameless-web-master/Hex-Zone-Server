"""CRUD for zone messages."""
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.zone_message import MessageVisibility, ZoneMessage


def create_zone_message(
    db: Session,
    *,
    zone_internal_id: int,
    sender_id: int,
    message: str,
    visibility: MessageVisibility,
    receiver_id: int | None,
) -> ZoneMessage:
    row = ZoneMessage(
        zone_id=zone_internal_id,
        sender_id=sender_id,
        receiver_id=receiver_id,
        visibility=visibility,
        message=message,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return row


def list_zone_messages_for_viewer(
    db: Session,
    *,
    zone_internal_id: int,
    viewer_owner_id: int,
    with_owner_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[ZoneMessage]:
    """Return messages visible to viewer_owner_id.

    Always includes every public message in the zone.

    Private messages: if with_owner_id is None, any private where the viewer is
    sender or receiver. If with_owner_id is set, only private messages in the
    thread between viewer and with_owner_id (plus all public).
    """
    public = ZoneMessage.visibility == MessageVisibility.PUBLIC

    if with_owner_id is None:
        private_mine = and_(
            ZoneMessage.visibility == MessageVisibility.PRIVATE,
            or_(
                ZoneMessage.sender_id == viewer_owner_id,
                ZoneMessage.receiver_id == viewer_owner_id,
            ),
        )
        visible = or_(public, private_mine)
    else:
        private_thread = and_(
            ZoneMessage.visibility == MessageVisibility.PRIVATE,
            or_(
                and_(
                    ZoneMessage.sender_id == viewer_owner_id,
                    ZoneMessage.receiver_id == with_owner_id,
                ),
                and_(
                    ZoneMessage.sender_id == with_owner_id,
                    ZoneMessage.receiver_id == viewer_owner_id,
                ),
            ),
        )
        visible = or_(public, private_thread)

    q = (
        select(ZoneMessage)
        .where(ZoneMessage.zone_id == zone_internal_id)
        .where(visible)
        .order_by(ZoneMessage.created_at.asc())
        .offset(skip)
        .limit(limit)
    )
    return list(db.execute(q).scalars().all())
