# API Specification

REST API contract for the ButterPOS AI Support Agent middleware. All endpoints live under `/api/v1/`.

---

## Versioning

- Base path: `/api/v1/`
- Breaking changes increment the version prefix (`/api/v2/`); v1 remains until deprecated.
- Router aggregation: `app/api/v1/router.py`

---

## Endpoints

### Auth (Task 1.1.2)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/auth/token` | Client credentials in body | Issue JWT access token |
| `GET` | `/api/v1/auth/me` | Bearer JWT | Return authenticated `subject` |

#### `POST /api/v1/auth/token`

**Request body:**

```json
{
  "client_id": "butterpos-widget",
  "client_secret": "<API_CLIENT_SECRET>",
  "subject": "staff-user-123"
}
```

**Response `200`:**

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Errors:** `401` invalid credentials · `503` JWT or client config missing

#### `GET /api/v1/auth/me`

**Headers:** `Authorization: Bearer <access_token>`

**Response `200`:**

```json
{
  "subject": "staff-user-123"
}
```

**Errors:** `401` missing, invalid, or expired token

#### `GET /api/v1/system/ticketing-health`

**Headers:** `Authorization: Bearer <access_token>`

**Response `200`:** `ProviderHealth` — live Chatwoot probe (`GET /api`) via `ChatwootAdapter.health_check()`; includes `latency_ms` when healthy.

### Webhooks (Task 1.4)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/webhooks/chatwoot` | HMAC (`X-Chatwoot-Signature`) | Receive Chatwoot account webhook |

#### `POST /api/v1/webhooks/chatwoot`

**Auth:** No JWT. Chatwoot signs the raw body with `CHATWOOT_WEBHOOK_SECRET`. See `WEBHOOKS.md`.

**Headers (required):**

| Header | Purpose |
|--------|---------|
| `X-Chatwoot-Signature` | `sha256=HMAC-SHA256(secret, "{timestamp}.{raw_body}")` |
| `X-Chatwoot-Timestamp` | Unix seconds — replay window enforced |

**Body:** Raw JSON bytes from Chatwoot (do not re-serialize before verify).

**Response `200`:**

```json
{
  "status": "accepted",
  "event_type": "message_created",
  "provider_event_id": "12345",
  "provider_ticket_id": "5678",
  "idempotency_key": "message_created:12345"
}
```

Duplicate replay (same `idempotency_key` already in `webhook_event_log`):

```json
{
  "status": "duplicate",
  "event_type": "message_created",
  "provider_event_id": "12345",
  "provider_ticket_id": "5678",
  "idempotency_key": "message_created:12345"
}
```

Both return HTTP `200` — Chatwoot must not retry on duplicates.

**Errors:** `401` invalid/missing signature · `400` malformed payload or missing idempotency key

**Implementation:** `app/api/v1/webhooks.py` → `WebhookService.receive_chatwoot()` → `record_webhook_event()` in `app/repositories/webhook_event_repository.py`.

Event processing and DLQ: Task 1.4 sub-steps 3+.

---

## Request/response schemas

Pydantic models: `app/schemas/auth.py`

| Model | Purpose |
|-------|---------|
| `TokenRequest` | Token issuance input |
| `TokenResponse` | Token issuance output |
| `AuthenticatedSubject` | Resolved JWT subject |
| `ErrorResponse` | Standard error body |

---

## Status mappings

`StandardStatus` (12 values) is the middleware canonical lifecycle. Chatwoot exposes **four** native statuses (`open`, `resolved`, `pending`, `snoozed`). The adapter maps between them and persists the canonical value in `custom_attributes.standard_status` when they diverge.

| StandardStatus | Chatwoot `toggle_status` | Notes |
|----------------|--------------------------|-------|
| `new` | `open` | |
| `open` | `open` | |
| `pending` | `pending` | |
| `in_progress` | `open` | Canonical value stored in `custom_attributes.standard_status` |
| `waiting_on_customer` | `pending` | Stored in `standard_status` |
| `waiting_on_internal` | `open` | Stored in `standard_status` |
| `escalated` | `open` | Stored in `standard_status` |
| `snoozed` | `snoozed` | |
| `on_hold` | `pending` | Stored in `standard_status` |
| `resolved` | `resolved` | |
| `closed` | `resolved` | Stored in `standard_status` |
| `reopened` | `open` | Stored in `standard_status` |

**Read path:** `chatwoot_status_to_standard()` prefers `custom_attributes.standard_status` when set; otherwise maps native Chatwoot status.

Implementation: `app/providers/ticketing/chatwoot/mappers.py`.

### `get_ticket()` / `update_status()` (Task 1.3.3)

| Method | Chatwoot API |
|--------|--------------|
| `get_ticket(id)` | `GET /conversations/{id}` → `StandardTicket` |
| `update_status(req)` | `POST /conversations/{id}/toggle_status` then `POST .../custom_attributes` then `GET` |

---

### `create_ticket()` (Task 1.3.2)

**Adapter:** `ChatwootAdapter.create_ticket(CreateTicketRequest) → StandardTicket`

| Standard field | Chatwoot source |
|----------------|-----------------|
| `provider_contact_id` | Request input → `contact_id` on `POST /conversations` |
| `provider_ticket_id` | Response `id` |
| `status` | Response `status` → `StandardStatus` via mapper |
| `subject` | Request `subject` → `custom_attributes.subject` + `StandardTicket.subject` |
| `initial_message` | `POST /conversations/{id}/messages` (outgoing, public) |
| `tags` | `POST /conversations/{id}/labels` |
| `metadata.source_id` | Request `metadata.source_id` or generated `butterpos-{contact_id}-{uuid}` |

Requires `CHATWOOT_INBOX_ID` (API-channel inbox). Implementation: `app/providers/ticketing/chatwoot/conversations.py`, `mappers.py`.

### `add_comment()` / `add_note()` (Task 1.3.4)

| Method | Chatwoot API | Visibility |
|--------|--------------|------------|
| `add_comment(req)` | `POST /conversations/{id}/messages` with `private: false` | Customer-visible AI reply |
| `add_note(req)` | `POST /conversations/{id}/messages` with `private: true` | Internal agent handoff note |

Optional rich UI on public comments via `AddCommentRequest.metadata`:

| Metadata key | Purpose |
|--------------|---------|
| `content_type` | e.g. `text`, `input_select` (Step 0.1 spike) |
| `content_attributes` | JSON object for buttons/cards — never URL-encoded string |

Notes always use plain `text`; no rich attributes.

### `assign_agent()` / `add_tags()` (Task 1.3.5)

| Method | Chatwoot API | Returns |
|--------|--------------|---------|
| `assign_agent(req)` | `POST /conversations/{id}/assignments` with `assignee_id` | Fresh `StandardTicket` |
| `add_tags(req)` | `GET` existing labels → merge → `POST .../labels` | `StandardTicket` with merged tags |

`assignee_id` and `provider_ticket_id` must be numeric Chatwoot ids (strings in standard model).

### `get_or_create_contact()` (Task 1.3.6)

**Adapter:** `ChatwootAdapter.get_or_create_contact(CreateContactRequest) → StandardContact`

| Standard field | Chatwoot source |
|----------------|-----------------|
| `external_user_id` | `identifier` on contact (ButterPOS `butterpos_user_id`) |
| `name` / `email` / `phone` | Same fields on create; used for filter/search |
| `provider_contact_id` | Chatwoot contact `id` |

**Lookup order:**

1. `POST /contacts/filter` — exact match on `identifier` (preferred)
2. `POST /contacts/filter` — exact match on `email` if provided
3. `GET /contacts/search?q=...` — fallback with exact match validation
4. `POST /contacts` with `inbox_id` — create if not found

Requires at least one of: `external_user_id`, `email`, or `phone`. Requires `CHATWOOT_INBOX_ID` for create.

Implementation: `app/providers/ticketing/chatwoot/contacts.py`.

### `verify_webhook()` / `parse_webhook()` / `register_webhook()` (Task 1.3.7)

| Method | Purpose |
|--------|---------|
| `verify_webhook(raw_body, headers)` | HMAC + timestamp validation |
| `parse_webhook(raw_body, headers)` | Event-specific JSON → `StandardEvent` + `idempotency_key` |
| `register_webhook(url)` | `POST /webhooks` on Chatwoot (adapter helper — not on `TicketingProvider` ABC) |

`parse_webhook` branches on `event` field (`message_*` vs `conversation_*` payload shapes). Unknown events map to `StandardEventType.UNKNOWN`.

---
