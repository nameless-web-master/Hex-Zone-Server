"""Authentication business logic for contract endpoints."""
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, generate_api_key, get_password_hash, verify_password
from app.models import Device, MemberLocation, Owner
from app.models.owner import OwnerRole
from app.services.access_policy import resolve_account_owner_id


def _to_contract_account_type(account_type: str) -> str:
    normalized = str(account_type).strip().lower()
    mapping = {
        "private": "PRIVATE",
        "private_plus": "PRIVATE_PLUS",
        "exclusive": "EXCLUSIVE",
        "enhanced": "ENHANCED",
        "enhanced_plus": "ENHANCED_PLUS",
    }
    contract_type = mapping.get(normalized)
    if contract_type is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported account type: {account_type}",
        )
    return contract_type


def _split_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split()
    if not parts:
        return "User", "User"
    if len(parts) == 1:
        return parts[0], "User"
    return parts[0], " ".join(parts[1:])


def _to_owner_role(registration_type: str | None) -> OwnerRole:
    normalized = str(registration_type or "ADMINISTRATOR").strip().upper().replace("-", "_").replace(" ", "_")
    if normalized in {"ADMIN", "ADMINISTRATOR"}:
        return OwnerRole.ADMINISTRATOR
    if normalized == "USER":
        return OwnerRole.USER
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Unsupported registration type: {registration_type}",
    )


def _get_map_center(db: Session, owner_id: int) -> dict | None:
    location = db.get(MemberLocation, owner_id)
    if location:
        return {"latitude": location.latitude, "longitude": location.longitude}

    device = (
        db.query(Device)
        .filter(
            Device.owner_id == owner_id,
            Device.latitude.isnot(None),
            Device.longitude.isnot(None),
        )
        .order_by(Device.updated_at.desc())
        .first()
    )
    if not device:
        return None
    return {"latitude": device.latitude, "longitude": device.longitude}


def register_user(db: Session, payload: dict) -> dict:
    existing = db.query(Owner).filter(Owner.email == payload["email"]).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    first_name, last_name = _split_name(payload["name"])
    account_type_value = _to_contract_account_type(payload["accountType"]).lower()
    role_value = _to_owner_role(payload.get("registrationType"))
    account_owner_id = resolve_account_owner_id(
        db,
        role=role_value.value,
        requested_account_owner_id=payload.get("accountOwnerId"),
        zone_id=payload.get("zoneId") or f"user-{payload['email']}",
        account_type=account_type_value,
    )
    owner = Owner(
        email=payload["email"],
        zone_id=payload.get("zoneId") or f"user-{payload['email']}",
        first_name=first_name,
        last_name=last_name,
        account_type=account_type_value,
        role=role_value,
        account_owner_id=account_owner_id,
        hashed_password=get_password_hash(payload["password"]),
        api_key=generate_api_key(),
        address=payload.get("address", "N/A"),
    )
    db.add(owner)
    db.flush()
    if owner.role.value == "administrator" and owner.account_owner_id is None:
        owner.account_owner_id = owner.id
        db.flush()
    db.refresh(owner)
    return {
        "id": str(owner.id),
        "email": owner.email,
        "zone_id": owner.zone_id,
        "first_name": owner.first_name,
        "last_name": owner.last_name,
        "account_type": owner.account_type.value,
        "role": owner.role.value,
        "account_owner_id": owner.account_owner_id or owner.id,
        "address": owner.address,
        "phone": owner.phone,
        "active": owner.active,
        "expired": owner.expired,
        "created_at": owner.created_at,
        "updated_at": owner.updated_at,
        "api_key": owner.api_key,
        "mapCenter": _get_map_center(db, owner.id),
    }


def login_user(db: Session, email: str, password: str) -> dict:
    owner = db.query(Owner).filter(Owner.email == email).first()
    if not owner or not verify_password(password, owner.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = create_access_token({"sub": str(owner.id)}, expires_delta=timedelta(minutes=30))
    return {
        "token": token,
        "user": {
            "id": str(owner.id),
            "name": f"{owner.first_name} {owner.last_name}".strip(),
            "accountType": _to_contract_account_type(owner.account_type.value),
            "registrationType": owner.role.value.upper(),
            "accountOwnerId": owner.account_owner_id or owner.id,
            "mapCenter": _get_map_center(db, owner.id),
        },
    }
