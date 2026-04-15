"""Auth controller."""
from app.schemas.schemas import LoginRequest, OwnerCreate
from app.services import auth_service


def register(db, payload: OwnerCreate):
    return auth_service.register_owner(db, payload)


def login(db, payload: LoginRequest):
    return auth_service.login_owner(db, payload)
