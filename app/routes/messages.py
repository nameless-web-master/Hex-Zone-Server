"""Message routes."""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.controllers import message_controller
from app.core.security import get_current_user
from app.crud import message as message_crud
from app.crud import owner as owner_crud
from app.database import get_db
from app.schemas.schemas import ZoneMessageCreate
from app.utils.api_response import success_response
from app.websocket.connection_manager import manager

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_message(payload: ZoneMessageCreate, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    message, zone_id = message_controller.create_message(db, current_user["user_id"], payload)
    response_payload = {
        "id": message.id,
        "zone_id": zone_id,
        "sender_id": message.sender_id,
        "receiver_id": message.receiver_id,
        "visibility": message.visibility.value,
        "message": message.message,
        "created_at": message.created_at.isoformat(),
    }
    await manager.broadcast_zone(zone_id, {"event": "message.created", "payload": response_payload})
    return success_response(response_payload, status_code=status.HTTP_201_CREATED)


@router.get("/")
@router.get("/new")
async def list_messages(
    owner_id: int = Query(..., ge=1),
    other_owner_id: int | None = Query(None, ge=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner = owner_crud.get_owner(db, current_user["user_id"])
    messages = message_crud.list_visible_messages(
        db,
        owner_id=owner_id,
        other_owner_id=other_owner_id,
        skip=skip,
        limit=limit,
    )
    data = [
        {
            "id": item.id,
            "zone_id": owner.zone_id if owner else "",
            "sender_id": item.sender_id,
            "receiver_id": item.receiver_id,
            "visibility": item.visibility.value,
            "message": item.message,
            "created_at": item.created_at.isoformat(),
        }
        for item in messages
    ]
    return success_response(data)
