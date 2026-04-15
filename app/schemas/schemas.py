"""Pydantic schemas for request/response validation."""
# UPDATED for Zoning-Messaging-System-Summary-v1.1.pdf
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import date, datetime, time
from enum import Enum


class AccountTypeEnum(str, Enum):
    """Account type enum."""
    PRIVATE = "private"
    EXCLUSIVE = "exclusive"
    GUARD = "guard"


class ZoneTypeEnum(str, Enum):
    """Zone type enum."""
    H3_HEX_GRID_ZONING = "h3_hex_grid_zoning"
    ZONE_MATCHING_COMMUNAL_ID = "zone_matching_communal_id"
    ZONE_MATCHING_GOVERNMENTAL_LOCAL_CODE = "zone_matching_governmental_local_code"
    OBJECT_ZONING = "object_zoning"
    GRID_ZONING = "grid_zoning"
    GEO_FENCE_ZONING = "geo_fence_zoning"
    PROXIMITY_TO_SOURCE_ZONING = "proximity_to_source_zoning"
    DYNAMIC_SIZE_ZONING = "dynamic_size_zoning"
    NO_ZONING = "no_zoning"


# ==================== OWNER SCHEMAS ====================

class OwnerBase(BaseModel):
    """Base owner schema."""
    email: EmailStr
    zone_id: str = Field(..., min_length=1, max_length=100)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    account_type: AccountTypeEnum = AccountTypeEnum.PRIVATE
    address: str = Field(..., min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)


class OwnerCreate(OwnerBase):
    """Owner creation schema."""
    password: str = Field(..., min_length=8)


class OwnerUpdate(BaseModel):
    """Owner update schema."""
    zone_id: Optional[str] = Field(None, min_length=1, max_length=100)
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    active: Optional[bool] = None


class OwnerResponse(OwnerBase):
    """Owner response schema."""
    id: int
    api_key: str
    active: bool
    expired: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OwnerDetailResponse(OwnerResponse):
    """Detailed owner response with relationships."""
    devices: List["DeviceResponse"] = []
    zones: List["ZoneResponse"] = []

    class Config:
        from_attributes = True


# ==================== DEVICE SCHEMAS ====================

class DeviceBase(BaseModel):
    """Base device schema."""
    hid: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=255)
    address: Optional[str] = None
    propagate_enabled: bool = True
    propagate_radius_km: float = Field(default=1.0, ge=0.1, le=50.0)
    enable_notification: bool = True
    alert_threshold_meters: float = Field(default=100.0, ge=1.0, le=1_000_000.0)
    update_interval_seconds: int = Field(default=60, ge=1, le=86400)


class DeviceLocationUpdate(BaseModel):
    """Device location update schema."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    address: Optional[str] = None


class DeviceCreate(DeviceBase):
    """Device creation schema."""
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)


class DeviceUpdate(BaseModel):
    """Device update schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    address: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    propagate_enabled: Optional[bool] = None
    propagate_radius_km: Optional[float] = Field(None, ge=0.1, le=50.0)
    active: Optional[bool] = None
    is_online: Optional[bool] = None
    enable_notification: Optional[bool] = None
    alert_threshold_meters: Optional[float] = Field(None, ge=1.0, le=1_000_000.0)
    update_interval_seconds: Optional[int] = Field(None, ge=1, le=86400)


class DeviceResponse(BaseModel):
    """Device response schema."""
    id: int
    hid: str
    device_id: str
    name: str
    latitude: Optional[float]
    longitude: Optional[float]
    address: Optional[str]
    h3_cell_id: Optional[str]
    owner_id: int
    propagate_enabled: bool
    propagate_radius_km: float
    active: bool
    is_online: bool
    last_seen: Optional[datetime]
    enable_notification: bool
    alert_threshold_meters: float
    update_interval_seconds: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== ZONE SCHEMAS ====================

class ZoneBase(BaseModel):
    """Base zone schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    zone_type: ZoneTypeEnum
    parameters: Optional[dict] = None


class ZoneCreate(ZoneBase):
    """Zone creation schema."""
    zone_id: str = Field(..., min_length=1, max_length=100)
    h3_cells: List[str] = Field(default_factory=list)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    h3_resolution: Optional[int] = Field(None, ge=0, le=15)
    geo_fence_polygon: Optional[dict] = None


class ZoneUpdate(BaseModel):
    """Zone update schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    zone_type: Optional[ZoneTypeEnum] = None
    parameters: Optional[dict] = None
    h3_cells: Optional[List[str]] = None
    geo_fence_polygon: Optional[dict] = None
    active: Optional[bool] = None


class ZoneResponse(BaseModel):
    """Zone response schema."""
    id: int
    zone_id: str
    owner_id: int
    zone_type: ZoneTypeEnum
    name: str
    description: Optional[str]
    h3_cells: List[str]
    geo_fence_polygon: Optional[dict] = None
    parameters: Optional[dict]
    active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== QR REGISTRATION SCHEMAS ====================

class QRRegistrationCreate(BaseModel):
    """QR registration creation schema."""
    expires_in_hours: int = Field(default=24, ge=1, le=720)


class QRRegistrationResponse(BaseModel):
    """QR registration response schema."""
    id: int
    token: str
    owner_id: int
    used: bool
    expires_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class QRRegistrationUse(BaseModel):
    """QR registration use schema (for joining account)."""
    token: str = Field(..., min_length=1)
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8)
    address: str = Field(..., min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)


# ==================== AUTH SCHEMAS ====================

class LoginRequest(BaseModel):
    """Login request schema."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Token response schema."""
    access_token: str
    token_type: str
    owner_id: int


# ==================== UTILITY SCHEMAS ====================

class H3ConversionRequest(BaseModel):
    """H3 conversion request schema."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    resolution: Optional[int] = Field(None, ge=0, le=15)


class H3ConversionResponse(BaseModel):
    """H3 conversion response schema."""
    latitude: float
    longitude: float
    h3_cell_id: str
    resolution: int


# ==================== ZONE MESSAGE SCHEMAS ====================


class MessageTypeEnum(str, Enum):
    """Supported message types."""

    PA = "PA"
    PRIVATE = "Private"
    SERVICE = "Service"
    WELLNESS = "Wellness"
    PANIC = "Panic"
    NS_PANIC = "NS Panic"
    UNKNOWN = "Unknown"
    SENSOR = "Sensor"


class ZoneMessageCreate(BaseModel):
    """Create a zone message."""

    message: str = Field(..., min_length=1, max_length=16_384)
    message_type: MessageTypeEnum = MessageTypeEnum.UNKNOWN
    receiver_id: Optional[int] = Field(
        None,
        ge=1,
        description="Required when message_type is Private; omitted for non-private message types",
    )


class ZoneMessageResponse(BaseModel):
    """Zone message returned to clients."""

    id: int
    zone_id: str = Field(..., description="Zone UUID (not the internal DB id)")
    sender_id: int
    receiver_id: Optional[int]
    message_type: MessageTypeEnum
    message: str
    created_at: datetime

    class Config:
        from_attributes = True


class EventBase(BaseModel):
    """Base event schema."""

    name: str = Field(..., min_length=1, max_length=255)
    date: date
    start_time: time
    end_time: time
    event_id: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    zone_id: str = Field(..., min_length=1, max_length=100)


class EventCreate(EventBase):
    """Create event schema."""


class EventUpdate(BaseModel):
    """Update event schema."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    event_id: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    zone_id: Optional[str] = Field(None, min_length=1, max_length=100)


class EventResponse(EventBase):
    """Event response schema."""

    id: int
    owner_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Update forward references
OwnerDetailResponse.model_rebuild()
