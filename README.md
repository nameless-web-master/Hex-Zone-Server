# Zone Weaver Backend API

FastAPI backend for Zone Weaver with JWT auth, owner/account policies, H3-powered zones, devices, messaging, and contract-compatible mobile routes.

## API Documentation

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## Quick Start

### Local development

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker

```bash
docker-compose up -d
```

## Authentication

This backend currently exposes two API styles:

1. **Core routes** (`/owners`, `/devices`, `/zones`, `/messages`, `/utils`)  
   - Auth uses bearer token from `POST /owners/login`.
2. **Contract routes** (for mobile/web wizard compatibility, e.g. `/login`, `/register`, `/members`)  
   - Auth uses bearer token from `POST /login`.

Use header:

```http
Authorization: Bearer <token>
```

## Core API Endpoints

### Health

- `GET /` - service info and docs link
- `GET /health` - health check

### Owners (`/owners`)

- `POST /owners/register` - register owner/user account
- `POST /owners/login` - login and return JWT
- `GET /owners/me` - get current authenticated owner profile
- `GET /owners/` - list caller-visible owners
- `GET /owners/{owner_id}` - get caller-visible owner by id
- `PATCH /owners/{owner_id}` - update owner profile (self)
- `DELETE /owners/{owner_id}` - delete owner profile (self)

### Devices (`/devices`)

- `POST /devices/` - create device
- `GET /devices/` - list caller-visible devices
- `GET /devices/{device_id}` - get device by numeric id
- `GET /devices/network/hid/{hid}` - get device by hardware id
- `PATCH /devices/{device_id}` - update device
- `POST /devices/{device_id}/location` - update location and H3 cell
- `POST /devices/{device_id}/heartbeat` - update online/last_seen presence
- `DELETE /devices/{device_id}` - delete device

### Zones (`/zones`)

- `POST /zones/` - create zone
- `GET /zones/` - list zones (supports `owner_id`, `zone_id`, `skip`, `limit`)
- `GET /zones/{zone_id}` - list zones by shared `zone_id` visible to caller
- `PATCH /zones/{zone_id}` - update zone
- `DELETE /zones/{zone_id}` - delete zone

### Messages (`/messages`)

- `POST /messages/` - create zone message (`public` or `private`)
- `GET /messages?owner_id={id}&other_owner_id={id?}&skip=0&limit=100` - list visible messages

Notes:
- `GET /messages` (no trailing slash) is canonical.
- `GET /messages/` is kept for backward compatibility (hidden from schema).

### Utilities (`/utils`)

- `POST /utils/h3/convert` - lat/lng to H3
- `POST /utils/qr/generate` - generate QR invite token (private accounts only)
- `POST /utils/qr/join` - register via QR invite token

## Contract API Endpoints

These routes align with setup wizard and mobile contract flows.

- `POST /login` - contract login
- `POST /register` - contract registration
- `GET /me` - contract owner profile
- `GET /zones` - list zones
- `POST /zones` - create zone
- `PUT /zones/{zone_id}` - update zone
- `DELETE /zones/{zone_id}` - delete zone
- `POST /messages` - create contract message (legacy payload or chat payload)
- `GET /messages/new?since=<iso-datetime>` - new messages since cursor
- `GET /members` - list visible members
- `POST /members/location` - upsert current member location
- `POST /devices/push-token` - register push token

## WebSocket Endpoints

- `GET /ws?token=<jwt>`
- `GET /ws/messages?token=<jwt>` (compat alias)

### WebSocket message contract

Client subscribe message:

```json
{
  "type": "SUBSCRIBE",
  "zoneIds": ["ZONE-7A29", "ZONE-3B19"]
}
```

Server ack:

```json
{
  "type": "SUBSCRIBED",
  "data": {
    "zoneIds": ["ZONE-3B19", "ZONE-7A29"]
  }
}
```

## Core Models

- **Owner**: account/user identity, role, account owner linkage, API key, zone id
- **Device**: hardware id, location, H3 cell, notification/presence settings
- **Zone**: shared `zone_id`, zone type, H3 cells, optional geofence polygon
- **ZoneMessage**: sender/receiver visibility model scoped by zone

## Useful cURL Examples

### Register + login (core owners)

```bash
curl -X POST http://localhost:8000/owners/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "zone_id": "ZONE-7A29",
    "first_name": "Avery",
    "last_name": "Stone",
    "account_type": "private",
    "role": "administrator",
    "address": "101 Main St, Denver, CO, USA",
    "password": "strong-password-123"
  }'

curl -X POST http://localhost:8000/owners/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "strong-password-123"
  }'
```

### Create zone (authenticated)

```bash
curl -X POST http://localhost:8000/zones/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "zone_id": "ZONE-7A29",
    "name": "Main Zone",
    "zone_type": "warn",
    "h3_cells": ["8928308280fffff"]
  }'
```

## Testing

```bash
pytest tests/ -v
```

## License

Proprietary - Zone Weaver Platform
