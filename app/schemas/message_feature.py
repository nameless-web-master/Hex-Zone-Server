"""Schemas for geo propagation, blocks, and permission schedules."""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from app.domain.message_types import CanonicalMessageType, normalize_message_type


class MessageFeatureType(str, Enum):
    SENSOR = CanonicalMessageType.SENSOR.value
    PANIC = CanonicalMessageType.PANIC.value
    NS_PANIC = CanonicalMessageType.NS_PANIC.value
    UNKNOWN = CanonicalMessageType.UNKNOWN.value
    PRIVATE = CanonicalMessageType.PRIVATE.value
    PA = CanonicalMessageType.PA.value
    SERVICE = CanonicalMessageType.SERVICE.value
    WELLNESS_CHECK = CanonicalMessageType.WELLNESS_CHECK.value
    PERMISSION = CanonicalMessageType.PERMISSION.value
    CHAT = CanonicalMessageType.CHAT.value


class CoordinatePayload(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class PropagationMessageCreate(BaseModel):
    type: MessageFeatureType
    hid: str = Field(..., min_length=1, max_length=255)
    tt: datetime = Field(default_factory=datetime.utcnow)
    msg: dict = Field(default_factory=dict)
    position: CoordinatePayload
    city: str | None = Field(default=None, max_length=120)
    province: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=120)
    to: str | None = Field(default=None, description="QR/access zone target")
    co: str | None = Field(default=None, description="Device zone id")
    receiver_owner_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="before")
    @classmethod
    def normalize_type_aliases(cls, data):
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        value = payload.get("type")
        if isinstance(value, str):
            payload["type"] = normalize_message_type(value).value
        return payload


class BlockRuleCreate(BaseModel):
    blocked_owner_id: int | None = Field(default=None, ge=1)
    blocked_message_type: MessageFeatureType | None = None

    @model_validator(mode="after")
    def validate_any_selector(self):
        if self.blocked_owner_id is None and self.blocked_message_type is None:
            raise ValueError("Either blocked_owner_id or blocked_message_type is required")
        return self


class BlockRuleResponse(BaseModel):
    id: int
    owner_id: int
    blocked_owner_id: int | None
    blocked_message_type: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AccessScheduleCreate(BaseModel):
    zone_id: str = Field(..., min_length=1, max_length=100)
    event_id: str | None = Field(default=None, max_length=100)
    guest_id: str | None = Field(default=None, max_length=100)
    guest_name: str | None = Field(default=None, max_length=255)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    notify_member_assist: bool = False


class AccessScheduleResponse(BaseModel):
    id: int
    zone_id: str
    event_id: str | None
    guest_id: str | None
    guest_name: str | None
    starts_at: datetime | None
    ends_at: datetime | None
    notify_member_assist: bool
    active: bool
    created_by_owner_id: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PermissionDecisionResponse(BaseModel):
    decision: str
    schedule_match: bool
    sender_message: dict
    member_message: dict
    delivered_owner_ids: list[int]


class PropagationMessageResponse(BaseModel):
    id: str
    type: str
    category: str | None = None
    scope: str | None = None
    zone_ids: list[str]
    delivered_owner_ids: list[int]
    blocked_owner_ids: list[int]
    created_at: str
