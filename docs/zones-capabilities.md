# Zones API capability contract

This backend enforces per-creator zone capacity (by `zones.creator_id` and role) and edit authorization in server-side policy.

## Policy defaults

- `MAX_ZONES_ADMINISTRATOR=2` — account administrators may create up to **2 primary zones**
- `MAX_ZONES_USER=1` — each invited member may create **1 secondary zone**
- Primary zones = geometries created by the network administrator
- Secondary zones = geometries created by invited members
- Listing visibility: administrators see account primary + all member secondaries; members see admin primary zones plus their own secondary

## Edit authorization

Option A is enforced: a caller may edit only zones they created (`creator_id == caller.id`).

## Naming policy

- `name` is required on create.
- `name` is trimmed before persistence.
- Valid length is `1..120`.
- Name must be unique within the account scope (administrator + linked users), case-insensitive.

## Capabilities endpoint

`GET /zones/capabilities` returns:

```json
{
  "role": "administrator",
  "can_create_zone": false,
  "remaining_total": 0,
  "remaining_for_role": 0,
  "max_total": 2,
  "reserved_for_standard_users": 1,
  "reason": "Maximum of 2 primary zones for administrators reached."
}
```
