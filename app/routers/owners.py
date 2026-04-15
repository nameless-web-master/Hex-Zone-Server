"""Router for Owner/User endpoints."""
# UPDATED for Zoning-Messaging-System-Summary-v1.1.pdf
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from app.database import get_db
from app.schemas.schemas import (
    AccountTypeEnum,
    OwnerCreate,
    OwnerResponse,
    OwnerUpdate,
    OwnerDetailResponse,
    LoginRequest,
    TokenResponse,
)
from app.crud import owner as owner_crud
from app.core.security import get_current_user, verify_password, create_access_token
from app.models import Owner
from datetime import timedelta

router = APIRouter(prefix="/owners", tags=["owners"])


@router.post("/register", response_model=OwnerResponse, status_code=status.HTTP_201_CREATED)
async def register_owner(
    owner: OwnerCreate,
    db: Session = Depends(get_db),
):
    """Register a new owner."""
    # Check if email already exists
    existing_owner = owner_crud.get_owner_by_email(db, owner.email)
    if existing_owner:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Guard accounts are single-user accounts.
    if owner.account_type == AccountTypeEnum.GUARD:
        same_zone_guard_count = db.execute(
            select(func.count()).select_from(Owner).where(
                Owner.zone_id == owner.zone_id,
                Owner.account_type == AccountTypeEnum.GUARD.value,
            )
        ).scalar_one()
        if same_zone_guard_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Guard accounts are single-user; this guard zone is already assigned",
            )
    
    # Create owner
    db_owner = owner_crud.create_owner(db, owner)
    db.commit()
    
    return OwnerResponse.model_validate(db_owner)


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    db: Session = Depends(get_db),
):
    """Login with email and password."""
    owner = owner_crud.get_owner_by_email(db, credentials.email)
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    if not verify_password(credentials.password, owner.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    if not owner.active or owner.expired:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive or expired",
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": str(owner.id)},
        expires_delta=access_token_expires,
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        owner_id=owner.id,
    )


@router.get("/me", response_model=OwnerDetailResponse)
async def get_current_owner(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current authenticated owner."""
    owner = owner_crud.get_owner(db, current_user["user_id"])
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Owner not found",
        )
    return OwnerDetailResponse.model_validate(owner)


@router.get("/{owner_id}", response_model=OwnerDetailResponse)
async def get_owner(
    owner_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get an owner by ID (requires authentication)."""
    owner = owner_crud.get_owner(db, owner_id)
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Owner not found",
        )
    return OwnerDetailResponse.model_validate(owner)


@router.get("/", response_model=list[OwnerResponse])
async def list_owners(
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all owners (requires authentication)."""
    owners = owner_crud.list_owners(db, skip=skip, limit=limit)
    return [OwnerResponse.model_validate(owner) for owner in owners]


@router.patch("/{owner_id}", response_model=OwnerResponse)
async def update_owner(
    owner_id: int,
    owner_update: OwnerUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an owner."""
    if current_user["user_id"] != owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this owner",
        )
    
    updated_owner = owner_crud.update_owner(db, owner_id, owner_update)
    if not updated_owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Owner not found",
        )
    
    db.commit()
    return OwnerResponse.model_validate(updated_owner)


@router.delete("/{owner_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_owner(
    owner_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an owner."""
    if current_user["user_id"] != owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this owner",
        )
    
    deleted = owner_crud.delete_owner(db, owner_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Owner not found",
        )
    
    db.commit()
