"""Router for utility endpoints."""
# UPDATED for Zoning-Messaging-System-Summary-v1.1.pdf
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.schemas import (
    H3ConversionRequest,
    H3ConversionResponse,
    QRRegistrationCreate,
    QRRegistrationResponse,
    QRRegistrationUse,
    OwnerResponse,
)
from app.core.h3_utils import lat_lng_to_h3_cell
from app.core.security import get_current_user
from app.crud import qr_registration as qr_crud
from app.crud import owner as owner_crud
from fastapi import HTTPException, status

router = APIRouter(prefix="/utils", tags=["utilities"])


@router.post("/h3/convert", response_model=H3ConversionResponse)
async def convert_to_h3(
    request: H3ConversionRequest,
):
    """Convert latitude/longitude to H3 cell ID."""
    h3_cell_id = lat_lng_to_h3_cell(
        request.latitude,
        request.longitude,
        request.resolution,
    )
    
    from app.core.h3_utils import get_h3_resolution
    resolution = get_h3_resolution(h3_cell_id)
    
    return H3ConversionResponse(
        latitude=request.latitude,
        longitude=request.longitude,
        h3_cell_id=h3_cell_id,
        resolution=resolution,
    )


@router.post("/qr/generate", response_model=QRRegistrationResponse)
async def generate_qr_registration(
    qr_request: QRRegistrationCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate QR registration token for inviting users (Private accounts only)."""
    owner = owner_crud.get_owner(db, current_user["user_id"])
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Owner not found",
        )
    
    # Only Private accounts can generate QR codes
    if owner.account_type != "private":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Private accounts can generate QR registration codes",
        )
    
    qr = qr_crud.create_qr_registration(
        db,
        current_user["user_id"],
        qr_request.expires_in_hours,
    )
    db.commit()
    
    return QRRegistrationResponse.model_validate(qr)


@router.post("/qr/join", response_model=OwnerResponse)
async def join_with_qr(
    qr_data: QRRegistrationUse,
    db: Session = Depends(get_db),
):
    """Join a Private account using QR registration token."""
    # Find QR registration by token
    qr = qr_crud.get_qr_registration(db, qr_data.token)
    if not qr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired QR registration token",
        )
    
    # Check if already used
    if qr.used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="QR registration token already used",
        )
    
    # Check if expired
    if qr.is_expired():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="QR registration token has expired",
        )
    
    # Ensure this token belongs to a private account owner
    owner = owner_crud.get_owner(db, qr.owner_id)
    if not owner or owner.account_type != "private":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid QR registration token",
        )
    
    # Check if email already exists
    existing = owner_crud.get_owner_by_email(db, qr_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    
    # Create new owner under Private account type
    from app.schemas.schemas import OwnerCreate, AccountTypeEnum
    new_owner_data = OwnerCreate(
        email=qr_data.email,
        # Enforce inviter zone ownership for all QR-based joins.
        zone_id=owner.zone_id,
        first_name=qr_data.first_name,
        last_name=qr_data.last_name,
        password=qr_data.password,
        account_type=AccountTypeEnum.PRIVATE,
        address=qr_data.address,
        phone=qr_data.phone,
    )
    
    new_owner = owner_crud.create_owner(db, new_owner_data)
    
    # Mark QR as used
    qr_crud.mark_qr_registration_used(db, qr.token)
    db.commit()
    
    return OwnerResponse.model_validate(new_owner)
