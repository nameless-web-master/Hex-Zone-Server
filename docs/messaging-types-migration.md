## Messaging Type Migration

### Canonical taxonomy

- Alarm: `SENSOR`, `PANIC`, `NS_PANIC`, `UNKNOWN`
- Alert: `PRIVATE`, `PA`, `SERVICE`, `WELLNESS_CHECK`
- Access: `PERMISSION`, `CHAT`

Derived scope:

- private: `PRIVATE`, `PERMISSION`, `CHAT`
- public: all remaining canonical types

### Backward compatibility

- Legacy payloads that send `visibility` without `type` are accepted temporarily.
  - `private` -> `PRIVATE`
  - `public` -> `SERVICE`
- Responses always return canonical `type`.
- Legacy compatibility path emits header `X-API-Deprecated`.

### Canonical response shape

All message records returned by messaging APIs include:

- `id`
- `zone_id` or `zoneId` (endpoint-native casing)
- `sender_id`
- `receiver_id` (nullable)
- `type` (canonical enum value)
- `category` (`Alarm` | `Alert` | `Access`)
- `scope` (`public` | `private`)
- `message` / `text` and optional structured body payload
- `created_at` / `createdAt`

### Deprecated aliases accepted on input

- `NS PANIC` -> `NS_PANIC`
- `WELLNESS CHECK` -> `WELLNESS_CHECK`
- `NORMAL` -> `SERVICE` (legacy compatibility)
