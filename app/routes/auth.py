"""Authentication routes."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.controllers import auth_controller
from app.database import get_db
from app.schemas.schemas import LoginRequest, OwnerCreate
from app.utils.api_response import success_response

router = APIRouter(tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
@router.post("/owners/register", status_code=status.HTTP_201_CREATED)
async def register(payload: OwnerCreate, db: Session = Depends(get_db)):
    owner = auth_controller.register(db, payload)
    return success_response(
        {
            "id": owner.id,
            "email": owner.email,
            "zone_id": owner.zone_id,
            "first_name": owner.first_name,
            "last_name": owner.last_name,
            "account_type": owner.account_type.value,
        },
        status_code=status.HTTP_201_CREATED,
    )


@router.post("/login")
@router.post("/owners/login")
async def login(payload: LoginRequest, db: Session = Depends(get_db)):
    token_data = auth_controller.login(db, payload)
    return success_response(token_data)
