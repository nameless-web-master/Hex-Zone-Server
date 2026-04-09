"""Sample data for testing and development."""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session_maker, init_db
from app.crud.owner import create_owner
from app.crud.device import create_device
from app.crud.zone import create_zone
from app.schemas.schemas import OwnerCreate, DeviceCreate, ZoneCreate, AccountTypeEnum, ZoneTypeEnum


async def load_sample_data():
    """Load sample data into database."""
    await init_db()
    
    async with async_session_maker() as db:
        print("Loading sample data...")
        
        # Create sample owners
        owner1_data = OwnerCreate(
            email="alice@example.com",
            first_name="Alice",
            last_name="Johnson",
            account_type=AccountTypeEnum.PRIVATE,
            password="SecurePassword123",
            phone="+1-555-0001",
            address="123 Market St, San Francisco, CA",
        )
        owner1 = await create_owner(db, owner1_data)
        print(f"✓ Created owner: {owner1.email}")
        
        owner2_data = OwnerCreate(
            email="bob@example.com",
            first_name="Bob",
            last_name="Smith",
            account_type=AccountTypeEnum.EXCLUSIVE,
            password="SecurePassword456",
            phone="+1-555-0002",
            address="456 Broadway, New York, NY",
        )
        owner2 = await create_owner(db, owner2_data)
        print(f"✓ Created owner: {owner2.email}")
        
        # Create sample devices for owner1
        device1_data = DeviceCreate(
            hid="DEVICE_SF_001",
            name="Main Device - San Francisco",
            latitude=37.7749,
            longitude=-122.4194,
            address="123 Market St, San Francisco, CA",
            propagate_enabled=True,
            propagate_radius_km=2.0,
        )
        device1 = await create_device(db, owner1.id, device1_data)
        print(f"✓ Created device: {device1.hid}")
        
        device2_data = DeviceCreate(
            hid="DEVICE_NYC_001",
            name="Secondary Device - New York",
            latitude=40.7128,
            longitude=-74.0060,
            address="456 Broadway, New York, NY",
            propagate_enabled=True,
            propagate_radius_km=1.5,
        )
        device2 = await create_device(db, owner1.id, device2_data)
        print(f"✓ Created device: {device2.hid}")
        
        # Create sample devices for owner2
        device3_data = DeviceCreate(
            hid="DEVICE_LON_001",
            name="Premium Device - London",
            latitude=51.5074,
            longitude=-0.1278,
            address="10 Downing St, London, UK",
            propagate_enabled=True,
            propagate_radius_km=3.0,
        )
        device3 = await create_device(db, owner2.id, device3_data)
        print(f"✓ Created device: {device3.hid}")
        
        # Create sample zones for owner1
        zone1_data = ZoneCreate(
            name="Downtown San Francisco",
            description="Major business district",
            zone_type=ZoneTypeEnum.WARN,
            h3_cells=["88283473fffffff"],  # Sample H3 cell
            latitude=37.7749,
            longitude=-122.4194,
            h3_resolution=13,
        )
        zone1 = await create_zone(db, owner1.id, zone1_data)
        print(f"✓ Created zone: {zone1.zone_id}")
        
        zone2_data = ZoneCreate(
            name="Financial District",
            description="High importance zone",
            zone_type=ZoneTypeEnum.ALERT,
            h3_cells=["882834673ffffff"],
            latitude=40.7128,
            longitude=-74.0060,
            h3_resolution=13,
        )
        zone2 = await create_zone(db, owner1.id, zone2_data)
        print(f"✓ Created zone: {zone2.zone_id}")
        
        # Create sample zone for owner2
        zone3_data = ZoneCreate(
            name="Restricted Area - Premium",
            description="Premium exclusive zone",
            zone_type=ZoneTypeEnum.RESTRICTED,
            h3_cells=["88283071fffffff"],
            latitude=51.5074,
            longitude=-0.1278,
            h3_resolution=13,
        )
        zone3 = await create_zone(db, owner2.id, zone3_data)
        print(f"✓ Created zone: {zone3.zone_id}")
        
        await db.commit()
        print("\n✅ Sample data loaded successfully!")
        print(f"\nSample Credentials:")
        print(f"  User 1: alice@example.com / SecurePassword123")
        print(f"  User 2: bob@example.com / SecurePassword456")


if __name__ == "__main__":
    asyncio.run(load_sample_data())
