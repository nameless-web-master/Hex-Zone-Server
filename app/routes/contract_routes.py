"""Contract-compatible routes."""
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.controllers import contract_controllers as controllers
from app.database import get_db
from app.middleware.auth import require_auth
from app.models import Owner
from app.utils.api_response import success_response
from app.websocket.manager import ws_manager

router = APIRouter(tags=["contract"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=8)
    accountType: Literal["PRIVATE", "EXCLUSIVE"]
    zoneId: str | None = None


class ZoneUpsertRequest(BaseModel):
    name: str
    type: Literal["polygon", "circle", "grid", "dynamic", "proximity", "object"]
    geometry: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)


class MessageCreateRequest(BaseModel):
    zoneId: str
    type: Literal["NORMAL", "PANIC", "NS_PANIC", "SENSOR"]
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemberLocationRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class PushTokenRequest(BaseModel):
    token: str = Field(min_length=10)
    platform: Literal["FCM", "APNS"] = "FCM"


@router.post("/login")
async def login(payload: LoginRequest, db: Session = Depends(get_db)):
    data = controllers.login(db, payload.model_dump())
    db.commit()
    return success_response(data)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    data = controllers.register(db, payload.model_dump())
    db.commit()
    return success_response(data)


@router.get("/zones")
async def get_zones(owner: Owner = Depends(require_auth), db: Session = Depends(get_db)):
    return success_response(controllers.list_zones(db, owner))


@router.get("/me")
async def get_me(owner: Owner = Depends(require_auth)):
    account_type = "EXCLUSIVE" if owner.account_type.value == "exclusive" else "PRIVATE"
    return success_response(
        {
            "id": str(owner.id),
            "name": f"{owner.first_name} {owner.last_name}".strip(),
            "accountType": account_type,
        }
    )


@router.post("/zones", status_code=status.HTTP_201_CREATED)
async def post_zones(
    payload: ZoneUpsertRequest,
    owner: Owner = Depends(require_auth),
    db: Session = Depends(get_db),
):
    data = controllers.create_zone(db, owner, payload.model_dump())
    db.commit()
    return success_response(data)


@router.put("/zones/{zone_id}")
async def put_zone(
    zone_id: str,
    payload: ZoneUpsertRequest,
    owner: Owner = Depends(require_auth),
    db: Session = Depends(get_db),
):
    data = controllers.update_zone(db, owner, zone_id, payload.model_dump())
    db.commit()
    return success_response(data)


@router.delete("/zones/{zone_id}")
async def remove_zone(zone_id: str, owner: Owner = Depends(require_auth), db: Session = Depends(get_db)):
    controllers.delete_zone(db, owner, zone_id)
    db.commit()
    return success_response({"deleted": True, "zoneId": zone_id})


@router.post("/messages", status_code=status.HTTP_201_CREATED)
async def post_messages(
    payload: MessageCreateRequest,
    owner: Owner = Depends(require_auth),
    db: Session = Depends(get_db),
):
    data = controllers.create_message(db, owner, payload.model_dump())
    db.commit()
    await ws_manager.broadcast_message(payload.zoneId, data)
    return success_response(data)


@router.get("/messages/new")
async def get_new_messages(since: str = Query(...), db: Session = Depends(get_db), owner: Owner = Depends(require_auth)):
    _ = owner
    return success_response(controllers.get_new_messages(db, since))


@router.get("/members")
async def get_members(owner: Owner = Depends(require_auth), db: Session = Depends(get_db)):
    return success_response(controllers.get_members(db, owner))


@router.post("/members/location")
async def post_member_location(
    payload: MemberLocationRequest,
    owner: Owner = Depends(require_auth),
    db: Session = Depends(get_db),
):
    data = controllers.update_location(db, owner, payload.latitude, payload.longitude)
    db.commit()
    return success_response(data)


@router.post("/devices/push-token")
async def post_push_token(
    payload: PushTokenRequest,
    owner: Owner = Depends(require_auth),
    db: Session = Depends(get_db),
):
    data = controllers.register_push_token(db, owner, payload.token, payload.platform)
    db.commit()
    return success_response(data)
