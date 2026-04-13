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
                "first_name": "Test",
                "last_name": "User",
                "account_type": "private",
                "password": "SecurePassword123",
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@example.com"
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
                "first_name": "Test",
                "last_name": "User",
                "account_type": "private",
                "password": "SecurePassword123",
            },
        )
        
        # Second registration with same email
        response = await client.post(
            "/owners/register",
            json={
                "email": "test@example.com",
                "first_name": "Test2",
                "last_name": "User2",
                "account_type": "private",
                "password": "SecurePassword123",
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
                "first_name": "Test",
                "last_name": "User",
                "account_type": "private",
                "password": "SecurePassword123",
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
                "first_name": "Test",
                "last_name": "User",
                "account_type": "private",
                "password": "SecurePassword123",
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
