"""CRUD operations for schedule access events."""
# UPDATED for Zoning-Messaging-System-Summary-v1.1.pdf
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.future import select
from app.models import Event
from app.schemas.schemas import EventCreate, EventUpdate


def create_event(db: Session, owner_id: int, payload: EventCreate) -> Event:
    """Create a new event."""
    db_event = Event(
        name=payload.name,
        date=payload.date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        event_id=payload.event_id,
        description=payload.description,
        zone_id=payload.zone_id,
        owner_id=owner_id,
    )
    db.add(db_event)
    db.flush()
    db.refresh(db_event)
    return db_event


def get_event(db: Session, event_id: int, owner_id: int) -> Optional[Event]:
    """Get event by id for owner."""
    result = db.execute(
        select(Event).where(Event.id == event_id, Event.owner_id == owner_id)
    )
    return result.scalars().first()


def list_events(db: Session, owner_id: int, skip: int = 0, limit: int = 100) -> list[Event]:
    """List events for owner."""
    result = db.execute(
        select(Event)
        .where(Event.owner_id == owner_id)
        .order_by(Event.date.asc(), Event.start_time.asc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


def update_event(db: Session, event_id: int, owner_id: int, payload: EventUpdate) -> Optional[Event]:
    """Update event by id for owner."""
    db_event = get_event(db, event_id, owner_id)
    if not db_event:
        return None

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_event, field, value)

    db.flush()
    db.refresh(db_event)
    return db_event


def delete_event(db: Session, event_id: int, owner_id: int) -> bool:
    """Delete event by id for owner."""
    db_event = get_event(db, event_id, owner_id)
    if not db_event:
        return False
    db.delete(db_event)
    return True
