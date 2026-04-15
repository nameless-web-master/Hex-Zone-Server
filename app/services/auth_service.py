"""Authentication business logic for contract endpoints."""
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, generate_api_key, get_password_hash, verify_password
from app.models import Owner


def _to_contract_account_type(account_type: str) -> str:
    return "EXCLUSIVE" if str(account_type).lower() == "exclusive" else "PRIVATE"


def _split_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split()
    if not parts:
        return "User", "User"
    if len(parts) == 1:
        return parts[0], "User"
    return parts[0], " ".join(parts[1:])


def register_user(db: Session, payload: dict) -> dict:
    existing = db.query(Owner).filter(Owner.email == payload["email"]).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    first_name, last_name = _split_name(payload["name"])
    owner = Owner(
        email=payload["email"],
        zone_id=payload.get("zoneId") or f"user-{payload['email']}",
        first_name=first_name,
        last_name=last_name,
        account_type=_to_contract_account_type(payload["accountType"]).lower(),
        hashed_password=get_password_hash(payload["password"]),
        api_key=generate_api_key(),
        address=payload.get("address", "N/A"),
    )
    db.add(owner)
    db.flush()
    db.refresh(owner)
    return {
        "id": str(owner.id),
        "name": f"{owner.first_name} {owner.last_name}".strip(),
        "accountType": _to_contract_account_type(owner.account_type.value),
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
        },
    }
