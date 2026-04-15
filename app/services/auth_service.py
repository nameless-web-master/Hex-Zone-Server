"""Authentication service."""
from datetime import timedelta
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.core.security import create_access_token, verify_password
from app.crud import owner as owner_crud
from app.schemas.schemas import LoginRequest, OwnerCreate


def register_owner(db: Session, payload: OwnerCreate):
    """Register owner with unique email constraint."""
    existing_owner = owner_crud.get_owner_by_email(db, payload.email)
    if existing_owner:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    owner = owner_crud.create_owner(db, payload)
    db.commit()
    return owner


def login_owner(db: Session, credentials: LoginRequest) -> dict:
    """Validate owner credentials and return token payload."""
    owner = owner_crud.get_owner_by_email(db, credentials.email)
    if not owner or not verify_password(credentials.password, owner.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not owner.active or owner.expired:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive or expired")

    token = create_access_token(data={"sub": str(owner.id)}, expires_delta=timedelta(minutes=30))
    return {"access_token": token, "token_type": "bearer", "owner_id": owner.id}
