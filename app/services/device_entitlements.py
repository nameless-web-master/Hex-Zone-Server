"""Account type constraints for devices and member invitations."""
from __future__ import annotations

from fastapi import HTTPException, status

from app.models import Owner


DEVICE_LIMITS_BY_ACCOUNT_TYPE: dict[str, int | None] = {
    "private": 1,
    "exclusive": 1,
    "private_plus": 10,
    "enhanced": 1,
    "enhanced_plus": None,
}


def max_devices_for_account_type(account_type: str) -> int | None:
    """Return max devices allowed per owner for an account type."""
    return DEVICE_LIMITS_BY_ACCOUNT_TYPE.get(str(account_type).strip().lower())


def assert_owner_device_capacity(owner: Owner, current_device_count: int) -> None:
    """Ensure owner has capacity to enroll another device."""
    max_devices = max_devices_for_account_type(owner.account_type.value)
    if max_devices is None:
        return
    if current_device_count >= max_devices:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Account type '{owner.account_type.value}' allows at most "
                f"{max_devices} device(s) per owner"
            ),
        )


def assert_account_allows_user_members(account_type: str) -> None:
    """Ensure account tier supports user-member registrations."""
    normalized = str(account_type).strip().lower()
    if normalized == "exclusive":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Exclusive accounts do not allow user members",
        )
