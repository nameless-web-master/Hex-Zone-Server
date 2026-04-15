"""Router for zone message endpoints."""
# UPDATED for Zoning-Messaging-System-Summary-v1.1.pdf
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.schemas import MessageTypeEnum, ZoneMessageCreate, ZoneMessageResponse
from app.crud import message as message_crud
from app.crud import owner as owner_crud
from app.core.security import get_current_user

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("/", response_model=ZoneMessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    payload: ZoneMessageCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a public or private zone message."""
    sender = owner_crud.get_owner(db, current_user["user_id"])
    if not sender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sender owner not found",
        )

    if payload.message_type == MessageTypeEnum.PRIVATE and payload.receiver_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="receiver_id is required when message_type is Private",
        )

    if payload.message_type != MessageTypeEnum.PRIVATE and payload.receiver_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="receiver_id must be omitted for non-private message types",
        )

    if payload.receiver_id is not None:
        receiver = owner_crud.get_owner(db, payload.receiver_id)
        if not receiver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Receiver owner not found",
            )
        if receiver.zone_id != sender.zone_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Receiver is not in the sender zone",
            )

    db_message = message_crud.create_message(db, sender_id=sender.id, payload=payload)
    db.commit()

    return ZoneMessageResponse(
        id=db_message.id,
        zone_id=sender.zone_id,
        sender_id=db_message.sender_id,
        receiver_id=db_message.receiver_id,
        message_type=db_message.message_type,
        message=db_message.message,
        created_at=db_message.created_at,
    )


@router.get("/", response_model=list[ZoneMessageResponse])
async def list_messages(
    owner_id: int = Query(..., ge=1),
    other_owner_id: int | None = Query(None, ge=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List zone-visible messages for an owner."""
    if owner_id != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: owner_id must match authenticated user",
        )

    owner = owner_crud.get_owner(db, owner_id)
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Owner not found",
        )

    if other_owner_id is not None:
        other_owner = owner_crud.get_owner(db, other_owner_id)
        if not other_owner:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="other_owner_id not found",
            )
        if other_owner.zone_id != owner.zone_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="other_owner_id is not in the same zone",
            )

    messages = message_crud.list_visible_messages(
        db,
        owner_id=owner_id,
        other_owner_id=other_owner_id,
        skip=skip,
        limit=limit,
    )
    return [
        ZoneMessageResponse(
            id=message.id,
            zone_id=owner.zone_id,
            sender_id=message.sender_id,
            receiver_id=message.receiver_id,
            message_type=message.message_type,
            message=message.message,
            created_at=message.created_at,
        )
        for message in messages
    ]
