"""Owner routes."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.crud import owner as owner_crud
from app.database import get_db
from app.schemas.schemas import OwnerUpdate
from app.utils.api_response import success_response

router = APIRouter(prefix="/owners", tags=["owners"])


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    owner = owner_crud.get_owner(db, current_user["user_id"])
    if not owner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Owner not found")
    return success_response(
        {
            "id": owner.id,
            "email": owner.email,
            "zone_id": owner.zone_id,
            "first_name": owner.first_name,
            "last_name": owner.last_name,
            "account_type": owner.account_type.value,
            "address": owner.address,
            "phone": owner.phone,
            "active": owner.active,
            "expired": owner.expired,
        }
    )


@router.get("/")
async def list_owners(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = current_user
    owners = owner_crud.list_owners(db, skip=skip, limit=limit)
    return success_response(
        [
            {
                "id": owner.id,
                "email": owner.email,
                "zone_id": owner.zone_id,
                "first_name": owner.first_name,
                "last_name": owner.last_name,
                "account_type": owner.account_type.value,
                "active": owner.active,
                "expired": owner.expired,
            }
            for owner in owners
        ]
    )


@router.patch("/{owner_id}")
async def update_owner(
    owner_id: int,
    payload: OwnerUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user["user_id"] != owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    owner = owner_crud.update_owner(db, owner_id, payload)
    if not owner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Owner not found")
    db.commit()
    return success_response({"id": owner.id, "email": owner.email, "zone_id": owner.zone_id})


@router.delete("/{owner_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_owner(owner_id: int, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user["user_id"] != owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    deleted = owner_crud.delete_owner(db, owner_id)
    if deleted:
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
