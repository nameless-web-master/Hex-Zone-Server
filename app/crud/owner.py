"""CRUD operations for Owner/User."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models import Owner
from app.schemas.schemas import OwnerCreate, OwnerUpdate
from app.core.security import get_password_hash, generate_api_key
from typing import Optional


async def create_owner(db: AsyncSession, owner: OwnerCreate) -> Owner:
    """Create a new owner."""
    api_key = generate_api_key()
    db_owner = Owner(
        email=owner.email,
        first_name=owner.first_name,
        last_name=owner.last_name,
        account_type=owner.account_type,
        hashed_password=get_password_hash(owner.password),
        api_key=api_key,
        phone=owner.phone,
        address=owner.address,
    )
    db.add(db_owner)
    await db.flush()
    await db.refresh(db_owner)
    return db_owner


async def get_owner(db: AsyncSession, owner_id: int) -> Optional[Owner]:
    """Get an owner by ID."""
    result = await db.execute(
        select(Owner)
        .where(Owner.id == owner_id)
        .options(selectinload(Owner.devices), selectinload(Owner.zones))
    )
    return result.scalars().first()


async def get_owner_by_email(db: AsyncSession, email: str) -> Optional[Owner]:
    """Get an owner by email."""
    result = await db.execute(select(Owner).where(Owner.email == email))
    return result.scalars().first()


async def get_owner_by_api_key(db: AsyncSession, api_key: str) -> Optional[Owner]:
    """Get an owner by API key."""
    result = await db.execute(select(Owner).where(Owner.api_key == api_key))
    return result.scalars().first()


async def list_owners(db: AsyncSession, skip: int = 0, limit: int = 100):
    """List all owners."""
    result = await db.execute(
        select(Owner)
        .offset(skip)
        .limit(limit)
        .options(selectinload(Owner.devices), selectinload(Owner.zones))
    )
    return result.scalars().all()


async def update_owner(db: AsyncSession, owner_id: int, owner_update: OwnerUpdate) -> Optional[Owner]:
    """Update an owner."""
    db_owner = await get_owner(db, owner_id)
    if not db_owner:
        return None
    
    update_data = owner_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_owner, field, value)
    
    await db.flush()
    await db.refresh(db_owner)
    return db_owner


async def delete_owner(db: AsyncSession, owner_id: int) -> bool:
    """Delete an owner."""
    db_owner = await get_owner(db, owner_id)
    if not db_owner:
        return False
    
    await db.delete(db_owner)
    return True


async def count_owners(db: AsyncSession) -> int:
    """Count all owners."""
    result = await db.execute(select(Owner))
    return len(result.scalars().all())
