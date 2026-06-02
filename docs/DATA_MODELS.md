# Data Models

PostgreSQL schema, Pydantic models, and platform-agnostic field conventions.

---

## Standard models (Pydantic — Task 1.1.5)

Platform-agnostic types used by `TicketingProvider` and webhook processing. Defined in `app/models/standard.py`.

### `StandardStatus` (12 values)

| Value | Meaning |
|-------|---------|
| `new` | Created, not yet triaged |
| `open` | Active, awaiting agent |
| `pending` | Awaiting external input |
| `in_progress` | Agent actively working |
| `waiting_on_customer` | Blocked on customer reply |
| `waiting_on_internal` | Blocked on internal team |
| `escalated` | Raised to senior support |
| `snoozed` | Temporarily deferred |
| `on_hold` | Paused (billing/plan hold) |
| `resolved` | Fix confirmed |
| `closed` | Terminal state |
| `reopened` | Previously closed, active again |

Chatwoot mapping table: Task 1.3 (`ChatwootAdapter`).

### `StandardEventType`

| Value | Source (Chatwoot) |
|-------|-------------------|
| `message_created` | `message_created` |
| `message_updated` | `message_updated` |
| `conversation_status_changed` | `conversation_status_changed` |
| `conversation_updated` | `conversation_updated` |
| `webwidget_triggered` | `webwidget_triggered` |
| `unknown` | Unrecognized events |

### Core models

| Model | Purpose |
|-------|---------|
| `StandardTicket` | Normalized ticket/conversation |
| `StandardContact` | Normalized customer contact |
| `StandardEvent` | Normalized webhook event |
| `ProviderHealth` | Adapter health check result |

### Request DTOs

| Model | Used by |
|-------|---------|
| `CreateTicketRequest` | `create_ticket()` |
| `CreateContactRequest` | `get_or_create_contact()` |
| `AddCommentRequest` | `add_comment()` — public |
| `AddNoteRequest` | `add_note()` — internal |
| `UpdateStatusRequest` | `update_status()` |
| `AssignAgentRequest` | `assign_agent()` |
| `AddTagsRequest` | `add_tags()` |

### Platform-agnostic field naming

| Field | Why |
|-------|-----|
| `provider_ticket_id` | Platform-native id (Chatwoot conversation id today) |
| `provider_contact_id` | Platform-native contact id — not `chatwoot_contact_id` |
| `provider_event_id` | Platform-native message/event id |

---

## ORM base (Task 1.2.1)

SQLAlchemy 2 async ORM lives under `app/db/`.

| Component | Path | Purpose |
|-----------|------|---------|
| `Base` | `app/db/base.py` | Declarative base for all tables |
| `TimestampMixin` | `app/db/base.py` | `id`, `created_at`, `updated_at` on every entity |
| Session | `app/db/session.py` | `create_async_engine` + `get_async_session()` dependency |

### TimestampMixin fields

| Column | Type | Notes |
|--------|------|-------|
| `id` | `BigInteger` PK | Auto-increment internal id |
| `created_at` | `timestamptz` | Set on insert (`server_default=now()`) |
| `updated_at` | `timestamptz` | Updated on change (`server_onupdate=now()`) |

**Pydantic vs ORM:** `app/models/standard.py` = API/ticketing contract (Chatwoot-agnostic). `app/db/models/` (Task 1.2.2+) = persisted Postgres tables.

Alembic migrations: Task 1.2.6.

---

## Tables (Task 1.2.2)

ORM models: `app/db/models/`. Migrations: Task 1.2.6.

### Entity relationship

```
Restaurant 1 ──< Branch 1 ──< User
```

Mapping chain for Task 1.6: `butterpos_user_id` → `branch` → `restaurant` → plan/payment checks.

### `restaurants`

| Column | Type | Description |
|--------|------|-------------|
| `id` | bigint PK | Internal id (TimestampMixin) |
| `butterpos_restaurant_id` | varchar(64) unique | External id from ButterPOS billing/export |
| `name` | varchar(255) | Display name |
| `plan_type` | varchar(32) | e.g. `8h`, `16h`, `24-7`, plan tier |
| `payment_due` | boolean | Unpaid → agent restrictions (Task 1.6) |
| `expiry` | timestamptz nullable | Plan expiry |
| `created_at` / `updated_at` | timestamptz | TimestampMixin |

### `branches`

| Column | Type | Description |
|--------|------|-------------|
| `id` | bigint PK | Internal id |
| `restaurant_id` | FK → restaurants | Parent tenant |
| `butterpos_branch_id` | varchar(64) unique | External branch id |
| `name` | varchar(255) | Branch name |
| `timezone` | varchar(64) | IANA timezone (default `Asia/Karachi`) |
| `devices` | jsonb | Registered tablet/device metadata list |
| `created_at` / `updated_at` | timestamptz | TimestampMixin |

### `users`

| Column | Type | Description |
|--------|------|-------------|
| `id` | bigint PK | Internal id |
| `butterpos_user_id` | varchar(64) unique | Tablet/staff id from ButterPOS app |
| `branch_id` | FK → branches nullable | Branch assignment (`NULL` = unassigned edge case) |
| `provider_contact_id` | varchar(128) unique nullable | Ticketing platform contact id (Chatwoot today) |
| `language_pref` | varchar(16) | e.g. `en`, `ur`, `roman_ur` |
| `created_at` / `updated_at` | timestamptz | TimestampMixin |

### Why `provider_contact_id` on User?

Keeps ticketing platform ids out of core naming — same field works if Chatwoot is swapped for Zoho (D-1). Middleware links ButterPOS user ↔ platform contact once; adapter reads/writes contact by this id.

---

## Tables (Task 1.2.3)

ORM models: `app/db/models/ticket_cache.py`, `app/db/models/ai_conversation.py`. Migrations: Task 1.2.6.

### Entity relationship (extended)

```
User 1 ──< TicketCache 1 ── 1 AIConversation
User 1 ──< AIConversation (denormalized for user-scoped queries)
```

Chatwoot remains system of record for support tickets. Postgres holds a **durable mirror** (polling fallback, webhook reconciliation) and **AI-only state** Chatwoot does not store.

### `ticket_cache`

| Column | Type | Description |
|--------|------|-------------|
| `id` | bigint PK | Internal id (TimestampMixin) |
| `provider_ticket_id` | varchar(128) unique | Platform conversation id (Chatwoot today) |
| `user_id` | FK → users nullable | Linked ButterPOS staff/tablet user |
| `status` | varchar(32) | `StandardStatus` value (see Pydantic enum) |
| `subject` | varchar(512) nullable | Ticket subject line |
| `provider_contact_id` | varchar(128) nullable | Platform contact id |
| `assignee_id` | varchar(128) nullable | Platform agent/assignee id |
| `tags` | jsonb | Classification labels |
| `meta` | jsonb | Extra mirror fields (`StandardTicket.metadata` equivalent) |
| `synced_at` | timestamptz nullable | Last successful sync from ticketing platform |
| `created_at` / `updated_at` | timestamptz | TimestampMixin |

**Note:** Redis hot cache (60s TTL) is Task 1.5. This table is the durable mirror that survives restarts and supports Celery polling reconciliation (Task 1.4).

### `ai_conversations`

| Column | Type | Description |
|--------|------|-------------|
| `id` | bigint PK | Internal id |
| `ticket_cache_id` | FK → ticket_cache unique | One AI session per cached ticket |
| `user_id` | FK → users nullable | Denormalized for user-scoped history queries |
| `messages_json` | jsonb | Full LLM conversation (roles, content, tool calls) |
| `confidence_history` | jsonb | Per-turn confidence scores + tier decisions (audit) |
| `created_at` / `updated_at` | timestamptz | TimestampMixin |

### JSONB shape (informal — validated at service layer)

**`messages_json`** — array of objects, e.g. `{role, content, timestamp, tool_calls?}`.

**`confidence_history`** — array of objects, e.g. `{turn, score, tier, model, timestamp}`.

Strict Pydantic schemas for these payloads are deferred to the agent loop (Phase 2); ORM stores flexible JSONB.

### Why a local ticket cache mirror?

| Reason | Detail |
|--------|--------|
| Webhook gaps | Celery polling reconciles platform ↔ local state (Task 1.4) |
| Provider isolation | Mirror uses `provider_*` fields — no Chatwoot columns in core |
| AI separation | Chatwoot stores customer messages; middleware stores LLM/tool audit separately |

---

## Relationships

See entity diagram above. Cascade: deleting a restaurant removes branches; branch delete sets user `branch_id` NULL.

---

## Customer/branch mapping chain

<!-- Task 1.6 implements lookup logic using these tables. -->
