"""OpenAPI schemas for public QR guest access (`/api/access/*`)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GuestArrivalLocation(BaseModel):
    """Optional GPS hint from the guest device."""

    lat: float = Field(..., ge=-90, le=90, description="Latitude (WGS84).")
    lng: float = Field(..., ge=-180, le=180, description="Longitude (WGS84).")


class GuestArrivalRequest(BaseModel):
    """Payload when a guest scans the zone QR (no JWT). Matches zone + schedule rules server-side."""

    zone_id: str = Field(..., min_length=1, max_length=100, description="Zone id from QR (`?zid=`).")
    guest_name: str = Field(..., min_length=1, max_length=255, description="Name entered by guest.")
    event_id: str | None = Field(
        default=None,
        max_length=100,
        description="Optional; matched against scheduled visits together with guest_name.",
    )
    device_id: str | None = Field(default=None, max_length=255, description="Optional client device fingerprint.")
    location: GuestArrivalLocation | None = Field(default=None, description="Optional coordinates.")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "zone_id": "Z123",
                    "guest_name": "John Doe",
                    "event_id": "EVT-optional",
                    "device_id": "ios-abc",
                    "location": {"lat": 40.7128, "lng": -74.006},
                }
            ]
        }
    )


class GuestZoneActionRequest(BaseModel):
    """Administrator approve or reject for an unexpected guest session."""

    guest_id: str = Field(..., min_length=1, max_length=36, description="Returned by POST /api/access/permission.")
    zone_id: str = Field(..., min_length=1, max_length=100, description="Must match the guest session zone.")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"guest_id": "550e8400-e29b-41d4-a716-446655440000", "zone_id": "Z123"}]
        }
    )


class GuestAccessHttpError(BaseModel):
    """Envelope returned by the global HTTP exception handler for structured errors."""

    status: Literal["error"] = Field(default="error", description="Always `error` for API failures.")
    message: str = Field(description="Human-readable explanation.")
    error_code: str = Field(description="Stable machine-readable code (e.g. INVALID_ZONE, FORBIDDEN).")


class GuestScanResponse(BaseModel):
    """Immediate response after POST /api/access/permission."""

    status: Literal["EXPECTED", "UNEXPECTED"] = Field(
        description="EXPECTED: matched active schedule in window. UNEXPECTED: no matching schedule."
    )
    message: str = Field(description="Guest-facing instruction text.")
    guest_id: str = Field(description="Opaque id for polling GET /api/access/session/{guest_id}.")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "EXPECTED",
                    "message": "You are expected. Please proceed.",
                    "guest_id": "550e8400-e29b-41d4-a716-446655440000",
                },
                {
                    "status": "UNEXPECTED",
                    "message": "You are not scheduled. Please wait for approval.",
                    "guest_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
                },
            ]
        }
    )


class GuestAdminDecisionResponse(BaseModel):
    """Body returned by POST /api/access/approve or /reject after a successful write."""

    status: Literal["APPROVED", "REJECTED"] = Field(description="Resolution broadcast to polling clients.")
    message: str = Field(description="Short confirmation shown to admin caller / echoed for logs.")
    guest_id: str = Field(description="Same guest id issued at arrival.")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"status": "APPROVED", "message": "Guest access approved.", "guest_id": "550e8400-e29b-41d4-a716-446655440000"}
            ]
        }
    )


class GuestAccessSessionListItem(BaseModel):
    """One QR arrival session returned to authenticated zone members."""

    id: int
    guest_id: str
    zone_id: str
    guest_name: str
    event_id: str | None = None
    device_id: str | None = None
    kind: str = Field(description="expected | unexpected")
    resolution: str | None = Field(description="pending | approved | rejected; null for expected arrivals.")
    schedule_id: int | None = None
    admin_owner_id: int | None = Field(description="Anchor admin for unexpected chat thread when set.")
    latitude: float | None = None
    longitude: float | None = None
    created_at: datetime
    guest_status: Literal["EXPECTED", "UNEXPECTED", "APPROVED", "REJECTED"] = Field(
        description="Derived guest-facing status (matches GET /api/access/session/{guest_id})."
    )


class GuestSessionPollResponse(BaseModel):
    """Poll shape for guests waiting on approval."""

    guest_id: str
    zone_id: str
    status: Literal["EXPECTED", "UNEXPECTED", "APPROVED", "REJECTED"] = Field(
        description="EXPECTED: scheduled guest; UNEXPECTED: still pending admin; APPROVED/REJECTED: resolved."
    )
    message: str

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "guest_id": "550e8400-e29b-41d4-a716-446655440000",
                    "zone_id": "Z123",
                    "status": "UNEXPECTED",
                    "message": "You are not scheduled. Please wait for approval.",
                }
            ]
        }
    )
