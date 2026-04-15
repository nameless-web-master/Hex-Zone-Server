"""Router for schedule access events."""
# UPDATED for Zoning-Messaging-System-Summary-v1.1.pdf
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.schemas import EventCreate, EventResponse, EventUpdate
from app.crud import event as event_crud
from app.crud import zone as zone_crud
from app.core.security import get_current_user

router = APIRouter(prefix="/events", tags=["events"])


@router.post("/", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new event for the authenticated owner."""
    zone = zone_crud.get_zone(db, zone_id=payload.zone_id, owner_id=current_user["user_id"])
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found",
        )

    db_event = event_crud.create_event(db, owner_id=current_user["user_id"], payload=payload)
    db.commit()
    return EventResponse.model_validate(db_event)


@router.get("/", response_model=list[EventResponse])
async def list_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List events for the authenticated owner."""
    events = event_crud.list_events(db, owner_id=current_user["user_id"], skip=skip, limit=limit)
    return [EventResponse.model_validate(event) for event in events]


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get an event by id."""
    event = event_crud.get_event(db, event_id=event_id, owner_id=current_user["user_id"])
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return EventResponse.model_validate(event)


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: int,
    payload: EventUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an event by id."""
    if payload.zone_id is not None:
        zone = zone_crud.get_zone(db, zone_id=payload.zone_id, owner_id=current_user["user_id"])
        if not zone:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found")

    event = event_crud.update_event(
        db,
        event_id=event_id,
        owner_id=current_user["user_id"],
        payload=payload,
    )
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    db.commit()
    return EventResponse.model_validate(event)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an event by id."""
    deleted = event_crud.delete_event(db, event_id=event_id, owner_id=current_user["user_id"])
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    db.commit()
