# API Specification

REST API contract for the ButterPOS AI Support Agent middleware. All endpoints live under `/api/v1/`.

---

## Versioning

- Base path: `/api/v1/`
- Breaking changes increment the version prefix (`/api/v2/`); v1 remains until deprecated.
- Router aggregation: `app/api/v1/router.py`

---

## Endpoints

### Summary

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/auth/token` | Client credentials | Issue JWT |
| `GET` | `/api/v1/auth/me` | Bearer JWT | Current subject |
| `GET` | `/api/v1/system/health` | None | Postgres + Redis readiness |
| `GET` | `/api/v1/system/ticketing-health` | Bearer JWT | Chatwoot adapter probe |
| `POST` | `/api/v1/webhooks/chatwoot` | HMAC | Inbound Chatwoot webhook |
| `GET` | `/api/v1/chat/health` | None | Remote MCP + OpenRouter readiness |
| `POST` | `/api/v1/chat/messages` | Bearer JWT | Chat message → LLM + remote MCP |
| `GET` | `/api/v1/chat/ui` | None | Local HTML test chat (dev only) |

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

#### `GET /api/v1/system/health`

**Auth:** None — readiness probe for load balancers and smoke tests.

**Response `200`:** `SystemHealthResponse` when Postgres and Redis are reachable.

**Response `503`:** Same shape when any component is unhealthy (`healthy: false`).

```json
{
  "healthy": true,
  "app": "ButterPOS Support Agent",
  "version": "0.1.0",
  "components": [
    {"name": "postgres", "healthy": true, "message": null},
    {"name": "redis", "healthy": true, "message": null}
  ]
}
```

#### `GET /api/v1/system/ticketing-health`

**Headers:** `Authorization: Bearer <access_token>`

**Response `200`:** `ProviderHealth` — live Chatwoot probe (`GET /api`) via `ChatwootAdapter.health_check()`; includes `latency_ms` when healthy.

### Chat (frontend ↔ middleware)

React widget / Kotlin tablet chat with the support agent. Middleware connects to a **remote MCP server** via `MCP_SERVER_URL` — it does not spawn a local MCP subprocess.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/chat/health` | None | Remote MCP connected + OpenRouter configured |
| `GET` | `/api/v1/chat/sessions/{conversation_id}` | Bearer JWT | Poll session history (human agent replies after escalation) |
| `POST` | `/api/v1/chat/messages` | Bearer JWT | Send message; agent loop runs LLM + MCP tools; persists session; optional Chatwoot escalation |

Implementation: `app/api/v1/chat.py`, `app/services/chat_service.py`, `app/services/agent_service.py`, `app/services/escalation_service.py`, `app/core/mcp/client.py`.

#### Frontend flow

1. `POST /api/v1/auth/token` — exchange `API_CLIENT_ID` / `API_CLIENT_SECRET` + `subject` for JWT
2. `POST /api/v1/chat/messages` — `Authorization: Bearer <token>`, body below
3. After escalation — poll `GET /api/v1/chat/sessions/{conversation_id}?since_index=N` every few seconds for human replies
4. Optional: `GET /api/v1/chat/health` — readiness before enabling chat UI

#### `GET /api/v1/chat/health`

**Response `200`:**

```json
{
  "ready": true,
  "mcp_tools": 12,
  "mcp_server_url": "http://127.0.0.1:3001/mcp",
  "mcp_transport": "streamable_http",
  "model": "openai/gpt-4o",
  "openrouter_configured": true
}
```

#### `POST /api/v1/chat/messages`

**Headers:** `Authorization: Bearer <access_token>`

**Request body:**

```json
{
  "message": "What is the price of chicken biryani?",
  "branch_id": "demo-branch-karachi",
  "history": [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello!"}],
  "conversation_id": "optional-client-id",
  "source": "test",
  "escalate": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | yes | User message (1–4000 chars) |
| `history` | array | no | Client-side history seed — ignored once server has stored turns for `conversation_id` |
| `branch_id` | string | no | Branch context for MCP tools; defaults to `AGENT_DEFAULT_BRANCH_ID` |
| `conversation_id` | string | no | Client session id; server generates UUID if omitted |
| `source` | `"android"` \| `"hq"` \| `"test"` | no | Client origin (default `test`) |
| `escalate` | boolean | no | Force Chatwoot escalation after this turn (default `false`) |

**Auto-escalation (no flag required):** agent error · customer keywords (`human agent`, `escalate`, `real person`, etc.).

**Response `200`:**

```json
{
  "reply": "Chicken Biryani is PKR 450 (PKR 522 with tax).",
  "model": "openai/gpt-4o-mini",
  "tool_calls": [{"tool_name": "search_menu_items", "arguments": {}, "result": "...", "success": true}],
  "pii_tokens_masked": 0,
  "error": null,
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "escalated": false,
  "provider_ticket_id": null,
  "escalation_reason": null,
  "forwarded_to_human": false
}
```

| Response field | Description |
|----------------|-------------|
| `conversation_id` | Server session id — send on subsequent turns |
| `escalated` | `true` if a Chatwoot ticket was created/updated this turn |
| `provider_ticket_id` | Chatwoot conversation id when escalated |
| `escalation_reason` | e.g. `client_requested_escalation`, `customer_requested_human`, `agent_error:…` |
| `forwarded_to_human` | `true` when session is escalated and message was sent to Chatwoot (no AI run) |
| `reply` (when `forwarded_to_human`) | Empty string — clients should show a persistent “human agent active” state, not a per-message ack bubble |

**After escalation:** further `POST /messages` forwards customer text to Chatwoot via `add_customer_message` (incoming on API channel). AI agent does not run.

#### `GET /api/v1/chat/sessions/{conversation_id}`

**Query:** `since_index` (int, default `0`) — return only messages from this index onward (for polling).

**Response `200`:**

```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "escalated",
  "provider_ticket_id": "5678",
  "message_count": 5,
  "messages": [
    {
      "role": "assistant",
      "content": "Checking your printer now…",
      "speaker": "human",
      "at": "2026-06-02T12:05:00Z"
    }
  ]
}
```

| `speaker` | Meaning |
|-----------|---------|
| `customer` | Widget user |
| `ai` | Middleware agent |
| `human` | Chatwoot support agent (relayed via webhook) |

**Errors:** `401` missing JWT · `404` session not found or wrong `jwt_subject`

**On escalation:** middleware creates a Chatwoot conversation (or appends a private note if already escalated), posts a **private note** with the full AI transcript + tool calls, adds a **public comment** with the customer-facing reply, tags `ai-escalated` + `source-{android|hq|test}`, sets status `escalated`, and assigns `CHATWOOT_AGENT_ID` when configured.

**Errors:** `401` missing JWT · `400` agent error with no reply

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

Rate-limited incoming message (quota exceeded):

```json
{
  "status": "rate_limited",
  "event_type": "message_created",
  "provider_event_id": "12346",
  "provider_ticket_id": "5678",
  "idempotency_key": "message_created:12346"
}
```

Also HTTP `200` — rate limits are not surfaced as `429` on the webhook path so Chatwoot does not retry storms.

**Errors:** `401` invalid/missing signature · `400` malformed payload or missing idempotency key

**Implementation:** `app/api/v1/webhooks.py` → `WebhookService.receive_chatwoot()` → `record_webhook_event()` → `InboundMessageRateLimiter.check()` in `app/repositories/webhook_event_repository.py` / `app/core/rate_limit/`.

Event processing and DLQ: Task 1.4 sub-steps 3+.

#### Processing pipeline (Task 1.4.3)

| Component | Path |
|-----------|------|
| Dispatcher | `app/services/webhook_dispatch.py` → Celery `webhook.process` |
| Processor stub | `app/services/webhook_processor.py` |
| DLQ store | `app/worker/dlq.py` |
| Celery tasks | `app/worker/tasks/webhook_tasks.py` |

#### Polling fallback (Task 1.4.4)

| Component | Path |
|-----------|------|
| Provider method | `TicketingProvider.list_tickets_updated_since()` |
| Chatwoot API | `POST /conversations/filter` (inbox + updated_at) |
| Reconciliation | `app/services/ticket_polling_service.py` |
| Postgres mirror | `app/repositories/ticket_cache_repository.py` |
| Beat task | `ticket.poll_reconcile` in `app/worker/tasks/polling_tasks.py` |

---

## Request/response schemas

Pydantic models: `app/schemas/auth.py`

| Model | Purpose |
|-------|---------|
| `TokenRequest` | Token issuance input |
| `TokenResponse` | Token issuance output |
| `AuthenticatedSubject` | Resolved JWT subject |
| `ErrorResponse` | Standard error body |
| `SystemHealthResponse` | Middleware readiness (`/system/health`) |
| `ComponentHealth` | Single dependency in readiness probe |

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

**Request dedup (Task 1.5.3):** When `metadata.client_request_id`, `source_id`, or `idempotency_key` is present, `DedupingTicketingProvider` returns the cached ticket for replays within TTL — prevents double-tap duplicate conversations.

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
