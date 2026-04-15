"""Member routes."""
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.controllers import member_controller
from app.core.security import get_current_user
from app.database import get_db
from app.services.device_service import upsert_push_token
from app.utils.api_response import success_response

router = APIRouter(prefix="/members", tags=["members"])


class MemberLocationRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class PushTokenRequest(BaseModel):
    token: str = Field(..., min_length=16, max_length=512)
    platform: str = Field(..., min_length=2, max_length=20)


@router.get("/")
async def get_members(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    _ = current_user
    return success_response(member_controller.list_members(db))


@router.post("/location")
async def update_member_location(
    payload: MemberLocationRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = member_controller.update_location(db, current_user["user_id"], payload.latitude, payload.longitude)
    return success_response(data)


@router.post("/devices/token")
async def register_push_token(
    payload: PushTokenRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = upsert_push_token(db, current_user["user_id"], payload.token, payload.platform.lower())
    return success_response(data)
