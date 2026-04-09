# Zone Weaver Backend - M1 (Backend Foundation)

**Zone Weaver** is a User-Defined Zone Message Distribution Platform that allows users to create custom geographic zones (using H3 hexagonal indexing) and manage devices within those zones.

## Overview

This is **Milestone 1 (M1)** - Backend Foundation, which includes:
- FastAPI backend with async SQLAlchemy 2.0
- PostgreSQL with PostGIS for geospatial data
- H3 hexagonal zone indexing (resolution 0-15, default 13)
- JWT authentication
- User registration & account management
- Device registration and management
- Zone CRUD with H3 cells and PostGIS geometry
- QR-Code registration flow for Private accounts
- API key-based access
- Full Swagger/OpenAPI documentation

## Quick Start

### Prerequisites

- Docker & Docker Compose
- PostgreSQL 14+ with PostGIS
- Python 3.10+ (for local development)

### Option 1: Docker Compose (Recommended)

```bash
# Start services
docker-compose up -d

# Wait for database to be ready
sleep 10

# Create first user
curl -X POST http://localhost:8000/owners/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "first_name": "Admin",
    "last_name": "User",
    "account_type": "exclusive",
    "password": "SecurePassword123"
  }'

# Login to get token
RESPONSE=$(curl -X POST http://localhost:8000/owners/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "SecurePassword123"
  }')

TOKEN=$(echo $RESPONSE | jq -r '.access_token')

# Access API documentation
open http://localhost:8000/docs
```

### Option 2: Local Development

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your database credentials

# Run migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Access API documentation
open http://localhost:8000/docs
```

## API Endpoints

### Authentication

```
POST /owners/register      - Register new owner
POST /owners/login         - Get JWT access token
GET  /owners/me           - Get current authenticated owner
```

### Owners

```
GET    /owners/           - List all owners
GET    /owners/{id}       - Get owner details
PATCH  /owners/{id}       - Update owner
DELETE /owners/{id}       - Delete owner
```

### Devices

```
POST   /devices/                    - Create device
GET    /devices/                    - List user's devices
GET    /devices/{id}                - Get device
GET    /devices/network/hid/{hid}   - Get device by hardware ID
PATCH  /devices/{id}                - Update device
POST   /devices/{id}/location       - Update device location (calculates H3)
DELETE /devices/{id}                - Delete device
```

### Zones

```
POST   /zones/        - Create zone (max 3 per user)
GET    /zones/        - List user's zones
GET    /zones/{id}    - Get zone details
PATCH  /zones/{id}    - Update zone
DELETE /zones/{id}    - Delete zone
```

### QR Registration (Private Accounts Only)

```
POST /utils/qr/generate   - Generate QR registration token
POST /utils/qr/join       - Join account with QR token and user details
```

For `/utils/qr/join`, request body must include:
- `token`
- `email`
- `first_name`
- `last_name`
- `password`
- `address`
- `phone` (optional)

### Utilities

```
POST /utils/h3/convert    - Convert lat/lng to H3 cell ID
GET  /health              - Health check
GET  /                    - Root endpoint
```

## Account Types

### Private Account
- Multiple users can join via QR code
- Allowed zone types: `warn`, `alert`, `geofence`
- Maximum 3 zones per user
- QR-Code registration allowed
- Use case: Team/shared accounts

### Exclusive Account
- Single user only
- Any zone type allowed
- Maximum 3 zones per user
- No QR-Code registration
- Use case: Personal/premium accounts

## Zone Types

The system supports 7 zone types:
- `warn` - Warning zones
- `alert` - Alert zones
- `geofence` - Geofence boundaries
- `emergency` - Emergency zones
- `restricted` - Restricted areas
- `custom_1` - Custom type 1
- `custom_2` - Custom type 2

## H3 Hexagonal Grid

Zone coverage uses [H3](https://h3geo.org/) - an open-source hexagonal hierarchical geospatial indexing system.

- **Resolution**: 0-15 (default: 13)
- **Resolution 13**: ~43m hex diameter (ideal for device tracking)
- **Zones store**: Array of H3 cell IDs + optional PostGIS polygon for exact boundaries

## Data Models

### Owner/User
```python
id: int (primary key)
email: str (unique)
first_name: str
last_name: str
account_type: enum(private|exclusive)
hashed_password: str
api_key: str (unique)
active: bool
expired: bool
created_at: datetime
updated_at: datetime
```

### Device
```python
id: int (primary key)
hid: str (hardware ID, unique)
name: str
latitude: float (optional)
longitude: float (optional)
address: str (optional)
h3_cell_id: str (auto-calculated from lat/lng)
owner_id: int (foreign key)
propagate_enabled: bool
propagate_radius_km: float
active: bool
created_at: datetime
updated_at: datetime
```

### Zone
```python
id: int (primary key)
zone_id: str (UUID, unique)
owner_id: int (foreign key)
zone_type: enum(warn|alert|geofence|emergency|restricted|custom_1|custom_2)
name: str
description: str (optional)
h3_cells: array (JSON array of H3 cell IDs)
geo_fence_polygon: PostGIS Geometry(POLYGON) (optional)
parameters: dict (JSON for flexibility)
active: bool
created_at: datetime
updated_at: datetime
```

## Configuration

Key settings in `app/core/config.py`:

```python
DATABASE_URL = "postgresql+asyncpg://..."
SECRET_KEY = "your-secret-key-change-in-production"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
H3_DEFAULT_RESOLUTION = 13
MAX_ZONES_PER_USER = 3
```

## Testing

Run the test suite:

```bash
pytest tests/ -v

# With coverage
pytest tests/ --cov=app --cov-report=html
```

Test coverage includes:
- Owner registration and login
- H3 conversion and validation
- Account validation
- Zone limit enforcement

## Project Structure

```
backend/
├── app/
│   ├── core/              # Configuration, security, H3 utilities
│   │   ├── config.py      # Settings
│   │   ├── security.py    # JWT, password hashing
│   │   └── h3_utils.py    # H3 functions
│   ├── models/            # SQLAlchemy models
│   │   ├── owner.py
│   │   ├── device.py
│   │   ├── zone.py
│   │   └── qr_registration.py
│   ├── schemas/           # Pydantic schemas
│   ├── crud/              # Database operations
│   ├── routers/           # API endpoints
│   ├── database.py        # Database setup
│   └── main.py            # FastAPI app
├── alembic/               # Database migrations
├── tests/                 # Test suite
├── docker-compose.yml     # Services: API, PostgreSQL
├── Dockerfile             # API container
├── requirements.txt       # Python dependencies
├── .env.example           # Environment template
└── README.md              # This file
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
DATABASE_URL=postgresql+asyncpg://zoneweaver:zoneweaver_pass@localhost:5432/zoneweaver
SECRET_KEY="your-secret-key-minimum-32-characters"
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
H3_DEFAULT_RESOLUTION=13
MAX_ZONES_PER_USER=3
```

## Database Migrations

Using Alembic for schema management:

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Revert last migration
alembic downgrade -1
```

## Development Workflow

1. Create a feature branch
2. Make changes to models/routes
3. Create migration: `alembic revision --autogenerate`
4. Run tests: `pytest tests/ -v`
5. Test API: Visit http://localhost:8000/docs
6. Commit and push

## Compliance

✅ **M1 Requirements Addressed**:
- FastAPI + PostgreSQL + PostGIS
- User registration (Private & Exclusive)
- Login / JWT authentication
- QR-Code registration flow
- Account type logic & validation
- H3 hex zone CRUD (resolution ≥ 0, default 13)
- Address → lat/lng → H3 conversion
- 3 zones per user enforcement
- Device registration & linking
- Zone type rules
- Full Swagger/OpenAPI documentation

❌ **Not in M1** (Future Milestones):
- Frontend/React UI (M2)
- Map visualization (M2)
- Docker deployment guide (M3)
- Production hardening (M3)

## API Example Workflows

### 1. Register & Create Zone

```bash
# Register owner
curl -X POST http://localhost:8000/owners/register -H "Content-Type: application/json" -d '{
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "account_type": "private",
  "password": "SecurePass123"
}'

# Login
curl -X POST http://localhost:8000/owners/login -H "Content-Type: application/json" -d '{
  "email": "user@example.com",
  "password": "SecurePass123"
}'  # Returns token

# Convert location to H3
curl -X POST http://localhost:8000/utils/h3/convert -H "Content-Type: application/json" -d '{
  "latitude": 37.7749,
  "longitude": -122.4194,
  "resolution": 13
}'

# Create zone
curl -X POST http://localhost:8000/zones \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Downtown SF",
    "description": "Downtown San Francisco",
    "zone_type": "warn",
    "h3_cells": ["h3_cell_id_from_convert_endpoint"]
  }'
```

### 2. Device Registration

```bash
# Create device
curl -X POST http://localhost:8000/devices \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "hid": "DEVICE_001",
    "name": "Main Device",
    "latitude": 37.7749,
    "longitude": -122.4194,
    "propagate_enabled": true,
    "propagate_radius_km": 1.5
  }'

# Update device location
curl -X POST http://localhost:8000/devices/DEVICE_ID/location \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 37.7750,
    "longitude": -122.4195,
    "address": "123 Main St, SF, CA"
  }'
```

## Troubleshooting

### Database Connection Error
```
Check DATABASE_URL in .env
Ensure PostgreSQL is running: docker ps | grep postgres
```

### PostGIS Extension Missing
```bash
# Inside PostgreSQL container
docker-compose exec postgres psql -U zoneweaver -d zoneweaver -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

### Port Already in Use
```bash
# Change port in docker-compose.yml
# Or kill existing process
lsof -i :8000
kill -9 <PID>
```

## Security Notes

- Change `SECRET_KEY` before production
- Use HTTPS in production
- Implement rate limiting
- Add CORS restrictions
- Use environment variables for sensitive data
- Validate all user inputs
- Consider API key rotation

## Next Steps (M2 & M3)

- **M2**: React frontend, map visualization, device tracking UI
- **M3**: Docker production setup, deployment guides, comprehensive testing

## Support & Documentation

- **API Docs**: http://localhost:8000/docs (Swagger UI)
- **ReDoc**: http://localhost:8000/redoc
- **H3 Docs**: https://h3geo.org/
- **FastAPI Docs**: https://fastapi.tiangolo.com/

## License

Proprietary - Zone Weaver Platform

---

**Built with ❤️ for Zone Weaver**
