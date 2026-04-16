"""Router for zone message endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.schemas import MessageVisibilityEnum, ZoneMessageCreate, ZoneMessageResponse
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

    if payload.visibility == MessageVisibilityEnum.PRIVATE and payload.receiver_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="receiver_id is required for private messages",
        )

    if payload.visibility == MessageVisibilityEnum.PUBLIC and payload.receiver_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="receiver_id must be omitted for public messages",
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
        visibility=db_message.visibility,
        message=db_message.message,
        created_at=db_message.created_at,
    )


async def _list_zone_messages_for_owner(
    *,
    owner_id: int,
    other_owner_id: int | None,
    skip: int,
    limit: int,
    current_user: dict,
    db: Session,
) -> list[ZoneMessageResponse]:
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

    rows = message_crud.list_visible_messages(
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
            visibility=message.visibility,
            message=message.message,
            created_at=message.created_at,
        )
        for message in rows
    ]


@router.get(
    "",
    response_model=list[ZoneMessageResponse],
    summary="List zone messages",
    description=(
        "List zone-visible messages for the authenticated owner. "
        "This path (GET /messages, no trailing slash) is the canonical list URL and "
        "matches contract-style clients; GET /messages/ is equivalent and retained for "
        "backward compatibility."
    ),
)
async def list_messages(
    owner_id: int = Query(..., ge=1),
    other_owner_id: int | None = Query(None, ge=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await _list_zone_messages_for_owner(
        owner_id=owner_id,
        other_owner_id=other_owner_id,
        skip=skip,
        limit=limit,
        current_user=current_user,
        db=db,
    )


@router.get(
    "/",
    response_model=list[ZoneMessageResponse],
    include_in_schema=False,
)
async def list_messages_trailing_slash(
    owner_id: int = Query(..., ge=1),
    other_owner_id: int | None = Query(None, ge=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Backward-compatible list URL (trailing slash)."""
    return await _list_zone_messages_for_owner(
        owner_id=owner_id,
        other_owner_id=other_owner_id,
        skip=skip,
        limit=limit,
        current_user=current_user,
        db=db,
    )
