"""Router for zone message endpoints."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.schemas import ZoneMessageCreate, ZoneMessageResponse
from app.crud import message as message_crud
from app.crud import owner as owner_crud
from app.core.security import get_current_user
from app.domain.message_types import MessageScope, normalize_message_type, type_category, type_scope

router = APIRouter(prefix="/messages", tags=["messages"])
logger = logging.getLogger(__name__)


@router.post(
    "/",
    response_model=ZoneMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create zone message",
    description="Create public/private chat messages scoped to the sender's zone.",
    responses={
        status.HTTP_403_FORBIDDEN: {
            "description": "Receiver is outside sender zone.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Sender or receiver owner was not found.",
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Message visibility/receiver rules were violated.",
        },
    },
    response_description="Created zone message payload.",
)
async def create_message(
    payload: ZoneMessageCreate,
    response: Response,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a typed zone message with derived scope."""
    sender = owner_crud.get_owner(db, current_user["user_id"])
    if not sender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "OWNER_NOT_FOUND", "message": "Sender owner not found"},
        )

    try:
        canonical_type = normalize_message_type(payload.type or "")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_code": "INVALID_MESSAGE_TYPE", "message": "Unsupported message type."},
        ) from exc
    derived_scope = type_scope(canonical_type)

    if payload.visibility is not None and not payload.type:
        logger.warning("Deprecated legacy visibility-only payload used on /messages endpoint")
        response.headers["X-API-Deprecated"] = "visibility-only payload is deprecated; send type"

    if derived_scope == MessageScope.PRIVATE and payload.receiver_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "MISSING_RECIPIENT_FOR_PRIVATE_TYPE",
                "message": "receiver_id is required for private-scope message types.",
            },
        )

    if derived_scope == MessageScope.PUBLIC and payload.receiver_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "INVALID_TYPE_SCOPE_COMBINATION",
                "message": "receiver_id must be omitted for public-scope message types.",
            },
        )

    if payload.receiver_id is not None:
        receiver = owner_crud.get_owner(db, payload.receiver_id)
        if not receiver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "RECEIVER_NOT_FOUND", "message": "Receiver owner not found"},
            )
        if receiver.zone_id != sender.zone_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": "RECEIVER_NOT_IN_ZONE",
                    "message": "Receiver is not in the sender zone",
                },
            )

    db_message = message_crud.create_message(db, sender_id=sender.id, payload=payload)
    db.commit()

    return ZoneMessageResponse(
        id=db_message.id,
        zone_id=sender.zone_id,
        sender_id=db_message.sender_id,
        receiver_id=db_message.receiver_id,
        type=db_message.message_type,
        category=type_category(canonical_type).value,
        scope=derived_scope.value,
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
            type=message.message_type,
            category=type_category(normalize_message_type(message.message_type)).value,
            scope=type_scope(normalize_message_type(message.message_type)).value,
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
    responses={
        status.HTTP_403_FORBIDDEN: {
            "description": "owner_id does not match authenticated user or other_owner_id is unauthorized.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Requested owner or other_owner_id was not found.",
        },
    },
    response_description="Caller-visible message list in zone scope.",
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
