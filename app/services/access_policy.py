"""Account visibility and ownership rules."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Owner
from app.models.owner import AccountType, OwnerRole


def account_root_id(owner: Owner) -> int:
    """Return the account holder id for an owner."""
    return owner.account_owner_id or owner.id


def resolve_account_owner_id(
    db: Session,
    *,
    role: str,
    requested_account_owner_id: int | None,
    zone_id: str,
    account_type: str,
) -> int | None:
    """Resolve account owner linkage for new owner registrations."""
    if role == "administrator":
        return None

    if requested_account_owner_id is not None:
        account_owner = db.get(Owner, requested_account_owner_id)
        if not account_owner:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account owner not found")
        if str(account_owner.role.value) != "administrator":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="account_owner_id must reference an administrator",
            )
        if str(account_owner.account_type.value) != account_type:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="account_owner_id account type mismatch",
            )
        return account_owner.id

    # Fallback to the matching administrator in the same main zone.
    account_owner = (
        db.query(Owner)
        .filter(
            Owner.zone_id == zone_id,
            Owner.account_type == AccountType(account_type),
            Owner.role == OwnerRole.ADMINISTRATOR,
            Owner.active.is_(True),
        )
        .order_by(Owner.id.asc())
        .first()
    )
    if account_owner is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="User registration requires an existing administrator account owner",
        )
    return account_owner.id


def visible_owner_ids(db: Session, owner: Owner) -> list[int]:
    """Return owners visible to caller based on role/account type rules."""
    if owner.role.value == "user":
        return [owner.id]

    root_id = account_root_id(owner)
    rows = (
        db.query(Owner.id)
        .filter(
            Owner.account_owner_id == root_id,
            Owner.active.is_(True),
        )
        .all()
    )
    owner_ids = [row[0] for row in rows]
    if owner.id not in owner_ids:
        owner_ids.append(owner.id)
    return owner_ids


def visible_zone_owner_ids(db: Session, owner: Owner) -> list[int]:
    """Return owners whose zones are visible to the caller.

    Private accounts are zone-collaborative: both administrator and users can
    view each other's zones/cells within the same account root.
    """
    if owner.account_type.value != "private":
        return visible_owner_ids(db, owner)

    root_id = account_root_id(owner)
    rows = (
        db.query(Owner.id)
        .filter(
            Owner.account_owner_id == root_id,
            Owner.active.is_(True),
        )
        .all()
    )
    owner_ids = [row[0] for row in rows]
    if owner.id not in owner_ids:
        owner_ids.append(owner.id)
    return owner_ids

