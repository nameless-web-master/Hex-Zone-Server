"""Tests for registration and H3 conversion."""
import pytest
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db
from app.core.h3_utils import lat_lng_to_h3_cell, validate_h3_cell
from app.crud.zone import geojson_to_wkt

# Test database URL
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def test_db():
    """Create test database session."""
    engine = create_engine(TEST_DATABASE_URL, echo=False)
    testing_session_maker = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    with testing_session_maker() as session:
        yield session
    
    # Drop tables
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def override_get_db(test_db):
    """Override the get_db dependency."""
    def _override_get_db():
        yield test_db
    
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_owner_registration(test_db, override_get_db):
    """Test owner registration."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/owners/register",
            json={
                "email": "test@example.com",
                "zone_id": "zone-user-1",
                "first_name": "Test",
                "last_name": "User",
                "account_type": "private",
                "password": "SecurePassword123",
                "address": "Test Address 1",
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["zone_id"] == "zone-user-1"
        assert data["first_name"] == "Test"
        assert data["last_name"] == "User"
        assert data["account_type"] == "private"
        assert "api_key" in data
        assert data["active"] is True


@pytest.mark.asyncio
async def test_owner_registration_duplicate_email(test_db, override_get_db):
    """Test owner registration with duplicate email."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # First registration
        await client.post(
            "/owners/register",
            json={
                "email": "test@example.com",
                "zone_id": "zone-user-1",
                "first_name": "Test",
                "last_name": "User",
                "account_type": "private",
                "password": "SecurePassword123",
                "address": "Test Address 1",
            },
        )
        
        # Second registration with same email
        response = await client.post(
            "/owners/register",
            json={
                "email": "test@example.com",
                "zone_id": "zone-user-2",
                "first_name": "Test2",
                "last_name": "User2",
                "account_type": "private",
                "password": "SecurePassword123",
                "address": "Test Address 2",
            },
        )
        
        assert response.status_code == 409
        assert "already registered" in response.json()["detail"]


@pytest.mark.asyncio
async def test_owner_login(test_db, override_get_db):
    """Test owner login."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Register
        await client.post(
            "/owners/register",
            json={
                "email": "test@example.com",
                "zone_id": "zone-user-1",
                "first_name": "Test",
                "last_name": "User",
                "account_type": "private",
                "password": "SecurePassword123",
                "address": "Test Address 1",
            },
        )
        
        # Login
        response = await client.post(
            "/owners/login",
            json={
                "email": "test@example.com",
                "password": "SecurePassword123",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "owner_id" in data


@pytest.mark.asyncio
async def test_owner_login_invalid_password(test_db, override_get_db):
    """Test owner login with invalid password."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Register
        await client.post(
            "/owners/register",
            json={
                "email": "test@example.com",
                "zone_id": "zone-user-1",
                "first_name": "Test",
                "last_name": "User",
                "account_type": "private",
                "password": "SecurePassword123",
                "address": "Test Address 1",
            },
        )
        
        # Login with wrong password
        response = await client.post(
            "/owners/login",
            json={
                "email": "test@example.com",
                "password": "WrongPassword",
            },
        )
        
        assert response.status_code == 401


class TestH3Conversion:
    """Test H3 conversion utilities."""
    
    def test_lat_lng_to_h3_cell(self):
        """Test latitude/longitude to H3 cell conversion."""
        lat, lng = 37.7749, -122.4194  # San Francisco
        h3_cell = lat_lng_to_h3_cell(lat, lng)
        
        assert isinstance(h3_cell, str)
        assert validate_h3_cell(h3_cell)
    
    def test_h3_cell_resolution_default(self):
        """Test H3 cell with default resolution."""
        lat, lng = 40.7128, -74.0060  # New York
        h3_cell = lat_lng_to_h3_cell(lat, lng)
        
        assert validate_h3_cell(h3_cell)
    
    def test_h3_cell_custom_resolution(self):
        """Test H3 cell with custom resolution."""
        lat, lng = 51.5074, -0.1278  # London
        h3_cell = lat_lng_to_h3_cell(lat, lng, resolution=8)
        
        assert validate_h3_cell(h3_cell)
    
    def test_invalid_h3_cell(self):
        """Test validation of invalid H3 cell."""
        assert not validate_h3_cell("invalid_cell")
        assert not validate_h3_cell("")

    def test_geojson_to_wkt_multipolygon(self):
        """GeoJSON MultiPolygon should convert to WKT."""
        geojson = {
            "type": "MultiPolygon",
            "coordinates": [[[[
                -73.9809036254883, 40.85409494874863
            ], [
                -74.0687942504883, 40.80943034560593
            ], [
                -73.93249511718751, 40.74757738563813
            ], [
                -73.8710403442383, 40.829429265624036
            ], [
                -73.9809036254883, 40.85409494874863
            ]]]]
        }
        wkt = geojson_to_wkt(geojson)
        assert wkt.startswith("MULTIPOLYGON((")
        assert "-73.9809036254883 40.85409494874863" in wkt
        assert wkt.endswith("))")

    def test_geojson_to_geometry_ewkt(self):
        """GeoJSON polygon should convert to SRID EWKT string."""
        from app.crud.zone import _geojson_to_geometry

        geojson = {
            "type": "Polygon",
            "coordinates": [[
                [-73.9809036254883, 40.85409494874863],
                [-74.0687942504883, 40.80943034560593],
                [-73.93249511718751, 40.74757738563813],
                [-73.9809036254883, 40.85409494874863],
            ]]
        }

        ewkt = _geojson_to_geometry(geojson)
        assert isinstance(ewkt, str)
        assert ewkt.startswith("SRID=4326;")
        assert "MULTIPOLYGON(((" in ewkt
        assert "-73.9809036254883 40.85409494874863" in ewkt

    def test_zone_model_geojson_validator(self):
        """Zone model should convert dict GeoJSON to EWKT on assignment."""
        from app.models.zone import Zone

        geojson = {
            "type": "MultiPolygon",
            "coordinates": [[[[
                -73.964424133, 40.875621535
            ], [
                -74.085273743, 40.79093771
            ], [
                -73.906059265, 40.787558505
            ], [
                -73.922538757, 40.852513065
            ], [
                -73.964767456, 40.87432352
            ], [
                -73.964424133, 40.875621535
            ]]]]
        }

        zone = Zone(
            zone_id="test-zone",
            owner_id=1,
            zone_type="geofence",
            name="Test Zone",
            description="desc",
            h3_cells=[],
            geo_fence_polygon=geojson,
            parameters={},
        )

        assert isinstance(zone.geo_fence_polygon, str)
        assert zone.geo_fence_polygon.startswith("SRID=4326;")
        assert "MULTIPOLYGON(((" in zone.geo_fence_polygon


@pytest.mark.asyncio
async def test_h3_conversion_endpoint(test_db, override_get_db):
    """Test H3 conversion API endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/utils/h3/convert",
            json={
                "latitude": 37.7749,
                "longitude": -122.4194,
                "resolution": 13,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["latitude"] == 37.7749
        assert data["longitude"] == -122.4194
        assert "h3_cell_id" in data
        assert "resolution" in data
        assert validate_h3_cell(data["h3_cell_id"])


async def _register_and_login(
    client: AsyncClient,
    *,
    email: str,
    zone_id: str,
    first_name: str,
    last_name: str,
) -> tuple[int, str]:
    register_response = await client.post(
        "/owners/register",
        json={
            "email": email,
            "zone_id": zone_id,
            "first_name": first_name,
            "last_name": last_name,
            "account_type": "private",
            "password": "SecurePassword123",
            "address": "Test Address 1",
        },
    )
    assert register_response.status_code == 201

    login_response = await client.post(
        "/owners/login",
        json={
            "email": email,
            "password": "SecurePassword123",
        },
    )
    assert login_response.status_code == 200
    return login_response.json()["owner_id"], login_response.json()["access_token"]


@pytest.mark.asyncio
async def test_qr_join_uses_inviter_zone_id(test_db, override_get_db):
    """QR join should always inherit inviter zone_id."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        _, inviter_token = await _register_and_login(
            client,
            email="inviter@example.com",
            zone_id="inviter-zone-id",
            first_name="Invite",
            last_name="Owner",
        )

        generate_response = await client.post(
            "/utils/qr/generate",
            headers={"Authorization": f"Bearer {inviter_token}"},
            json={"expires_in_hours": 24},
        )
        assert generate_response.status_code == 200
        token = generate_response.json()["token"]

        join_response = await client.post(
            "/utils/qr/join",
            json={
                "token": token,
                "email": "joined@example.com",
                "first_name": "Joined",
                "last_name": "User",
                "password": "SecurePassword123",
                "address": "Joined Address",
            },
        )
        assert join_response.status_code == 200
        joined_owner = join_response.json()
        assert joined_owner["zone_id"] == "inviter-zone-id"


@pytest.mark.asyncio
async def test_zone_messages_visibility_and_filtering(test_db, override_get_db):
    """Messages should return public + private related to requester."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        owner_1_id, owner_1_token = await _register_and_login(
            client,
            email="owner1@example.com",
            zone_id="shared-zone",
            first_name="Owner",
            last_name="One",
        )
        owner_2_id, _ = await _register_and_login(
            client,
            email="owner2@example.com",
            zone_id="shared-zone",
            first_name="Owner",
            last_name="Two",
        )
        _, owner_3_token = await _register_and_login(
            client,
            email="owner3@example.com",
            zone_id="shared-zone",
            first_name="Owner",
            last_name="Three",
        )
        _, owner_4_token = await _register_and_login(
            client,
            email="owner4@example.com",
            zone_id="shared-zone",
            first_name="Owner",
            last_name="Four",
        )

        headers_owner_1 = {"Authorization": f"Bearer {owner_1_token}"}
        headers_owner_3 = {"Authorization": f"Bearer {owner_3_token}"}
        headers_owner_4 = {"Authorization": f"Bearer {owner_4_token}"}

        response = await client.post(
            "/messages/",
            headers=headers_owner_1,
            json={
                "message": "Public from owner 1",
                "visibility": "public",
            },
        )
        assert response.status_code == 201

        response = await client.post(
            "/messages/",
            headers=headers_owner_4,
            json={
                "message": "Public from owner 4",
                "visibility": "public",
            },
        )
        assert response.status_code == 201

        response = await client.post(
            "/messages/",
            headers=headers_owner_1,
            json={
                "message": "Private 1 -> 2",
                "visibility": "private",
                "receiver_id": owner_2_id,
            },
        )
        assert response.status_code == 201

        response = await client.post(
            "/messages/",
            headers=headers_owner_3,
            json={
                "message": "Private 3 -> 2 (not visible to owner 1)",
                "visibility": "private",
                "receiver_id": owner_2_id,
            },
        )
        assert response.status_code == 201

        response = await client.get(
            f"/messages/?owner_id={owner_1_id}",
            headers=headers_owner_1,
        )
        assert response.status_code == 200
        messages = response.json()
        message_texts = [entry["message"] for entry in messages]

        assert "Public from owner 1" in message_texts
        assert "Public from owner 4" in message_texts
        assert "Private 1 -> 2" in message_texts
        assert "Private 3 -> 2 (not visible to owner 1)" not in message_texts

        response = await client.get(
            f"/messages/?owner_id={owner_1_id}&other_owner_id={owner_2_id}",
            headers=headers_owner_1,
        )
        assert response.status_code == 200
        filtered_message_texts = [entry["message"] for entry in response.json()]
        assert "Public from owner 1" in filtered_message_texts
        assert "Private 1 -> 2" in filtered_message_texts
        assert "Public from owner 4" not in filtered_message_texts


@pytest.mark.asyncio
async def test_get_zone_returns_all_matching_zone_id_entries(test_db, override_get_db):
    """Fetching /zones/{zone_id} should return all matching zones across owners."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        _, owner_1_token = await _register_and_login(
            client,
            email="zones-owner1@example.com",
            zone_id="shared-zone",
            first_name="Owner",
            last_name="One",
        )
        _, owner_2_token = await _register_and_login(
            client,
            email="zones-owner2@example.com",
            zone_id="shared-zone",
            first_name="Owner",
            last_name="Two",
        )
        _, owner_3_token = await _register_and_login(
            client,
            email="zones-owner3@example.com",
            zone_id="other-zone",
            first_name="Owner",
            last_name="Three",
        )

        create_payload = {
            "zone_id": "shared-zone-id-value",
            "zone_type": "warn",
            "name": "Shared Zone",
            "description": "Shared",
            "h3_cells": [],
        }

        response = await client.post(
            "/zones/",
            headers={"Authorization": f"Bearer {owner_1_token}"},
            json=create_payload,
        )
        assert response.status_code == 201

        response = await client.post(
            "/zones/",
            headers={"Authorization": f"Bearer {owner_2_token}"},
            json=create_payload,
        )
        assert response.status_code == 201

        response = await client.post(
            "/zones/",
            headers={"Authorization": f"Bearer {owner_3_token}"},
            json={
                **create_payload,
                "zone_id": "other-zone-id-value",
                "name": "Other Zone",
            },
        )
        assert response.status_code == 201

        response = await client.get(
            "/zones/shared-zone-id-value",
            headers={"Authorization": f"Bearer {owner_1_token}"},
        )
        assert response.status_code == 200
        zones = response.json()
        assert isinstance(zones, list)
        assert len(zones) == 2
        assert all(zone["zone_id"] == "shared-zone-id-value" for zone in zones)


@pytest.mark.asyncio
async def test_list_zones_with_zone_id_query_returns_all_matching_entries(test_db, override_get_db):
    """GET /zones/?zone_id=... should return all matching zones across owners."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        _, owner_1_token = await _register_and_login(
            client,
            email="query-owner1@example.com",
            zone_id="shared-zone",
            first_name="Owner",
            last_name="One",
        )
        _, owner_2_token = await _register_and_login(
            client,
            email="query-owner2@example.com",
            zone_id="shared-zone",
            first_name="Owner",
            last_name="Two",
        )

        payload = {
            "zone_id": "ZN-80BJC1",
            "zone_type": "warn",
            "name": "Operations Zone",
            "description": "Zone from dashboard console.",
            "h3_cells": ["862a1008fffffff"],
        }

        response = await client.post(
            "/zones/",
            headers={"Authorization": f"Bearer {owner_1_token}"},
            json=payload,
        )
        assert response.status_code == 201

        response = await client.post(
            "/zones/",
            headers={"Authorization": f"Bearer {owner_2_token}"},
            json=payload,
        )
        assert response.status_code == 201

        response = await client.get(
            "/zones/?zone_id=ZN-80BJC1",
            headers={"Authorization": f"Bearer {owner_1_token}"},
        )
        assert response.status_code == 200
        zones = response.json()
        assert len(zones) == 2
        assert all(zone["zone_id"] == "ZN-80BJC1" for zone in zones)
