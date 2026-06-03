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

Chatwoot mapping table: Task 1.3 (`ChatwootAdapter`) — see `API_SPEC.md` for full 12-value ↔ 4-value mapping. Native Chatwoot statuses: `open`, `resolved`, `pending`, `snoozed`. Non-native StandardStatus values round-trip via `custom_attributes.standard_status`.

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

Alembic migrations: Task 1.2.6 — revision `20260602_0001` (`alembic upgrade head`).

---

## Migrations (Task 1.2.6)

| Item | Location |
|------|----------|
| Alembic config | `alembic.ini` |
| Environment | `alembic/env.py` — loads `DATABASE_URL`, converts `+asyncpg` → `+psycopg2` |
| Initial revision | `alembic/versions/20260602_0001_initial_schema.py` |
| URL helper | `app/db/url.py` → `to_sync_database_url()` |

**Apply locally:**

```bash
docker compose up -d
alembic upgrade head
alembic current   # should show 20260602_0001 (head)
```

**New migration (after ORM changes):**

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

Runtime app uses `postgresql+asyncpg://`; Alembic uses sync `psycopg2` (both in `requirements.txt`).

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

---

## Tables (Phase 2.1 — chat persistence)

ORM model: `app/db/models/chat_session.py`. Migration: `20260602_0002_chat_sessions`.

### Why `chat_sessions` alongside `ai_conversations`?

| Table | Purpose |
|-------|---------|
| `chat_sessions` | **Proactive** AI chat from Android/HQ widgets — no Chatwoot ticket until escalation |
| `ai_conversations` | **Reactive** AI tied to an existing `ticket_cache` row (webhook-driven support tickets) |

Both store LLM/tool audit in Postgres; Chatwoot remains system of record for human support after escalation only.

### Entity relationship

```
JWT subject (widget user) 1 ──< ChatSession (many sessions per user)
ChatSession 0..1 ── provider_ticket_id ──> Chatwoot conversation (after escalation)
```

### `chat_sessions`

| Column | Type | Description |
|--------|------|-------------|
| `id` | bigint PK | Internal id (TimestampMixin) |
| `external_id` | varchar(64) unique | Client/server session id (UUID) |
| `jwt_subject` | varchar(128) | JWT `sub` — widget user identity |
| `source` | varchar(16) | `android`, `hq`, or `test` |
| `branch_id` | varchar(128) nullable | Branch context for MCP tools |
| `status` | varchar(32) | `active` or `escalated` |
| `provider_ticket_id` | varchar(128) nullable | Chatwoot conversation id after escalation |
| `provider_contact_id` | varchar(128) nullable | Chatwoot contact id |
| `messages_json` | jsonb | Full turn history — see shape below |
| `meta` | jsonb | Escalation reason, timestamps, extensible metadata |
| `created_at` / `updated_at` | timestamptz | TimestampMixin |

### `messages_json` shape (validated in `app/schemas/chat_session.py`)

Array of turns:

```json
{
  "role": "user | assistant",
  "content": "...",
  "at": "2026-06-02T12:00:00Z",
  "tool_calls": [
    {"tool_name": "...", "arguments": {}, "result": "...", "success": true}
  ]
}
```

Service layer: `ChatSessionRepository`, `ChatService`, `EscalationService`.

### Why a local ticket cache mirror?

| Reason | Detail |
|--------|--------|
| Webhook gaps | Celery polling reconciles platform ↔ local state (Task 1.4) |
| Provider isolation | Mirror uses `provider_*` fields — no Chatwoot columns in core |
| AI separation | Chatwoot stores customer messages; middleware stores LLM/tool audit separately |

---

## Tables (Task 1.2.4)

ORM models: `app/db/models/kb_article.py`, `app/db/models/kb_article_version.py`. Migrations: Task 1.2.6.

### Entity relationship

```
KBArticle 1 ──< KBArticleVersion (immutable snapshots, ordered by version_number)
```

Live content lives on `kb_articles` for fast RAG retrieval. Every edit appends a `kb_article_versions` row; rollback copies a prior snapshot forward as a new version (never mutates history).

### `kb_articles`

| Column | Type | Description |
|--------|------|-------------|
| `id` | bigint PK | Internal id (TimestampMixin) |
| `slug` | varchar(128) unique | URL-safe identifier for lookup / RAG |
| `title` | varchar(255) | Display title (current) |
| `category` | varchar(64) | e.g. `network`, `printer`, `billing` (from MVP audit) |
| `status` | varchar(16) | `draft`, `published`, `archived` |
| `content_en` | text | Current English body |
| `content_ur` | text nullable | Current Roman Urdu / Urdu body |
| `current_version` | integer | Latest version number (matches newest snapshot) |
| `author` | varchar(128) nullable | Content owner (from MVP sheet) |
| `roman_urdu_needed` | boolean | Flag from Step 0.3 MVP template |
| `tags` | jsonb | Search/classification labels |
| `published_at` | timestamptz nullable | When first/last published |
| `created_at` / `updated_at` | timestamptz | TimestampMixin |

### `kb_article_versions`

| Column | Type | Description |
|--------|------|-------------|
| `id` | bigint PK | Internal id |
| `article_id` | FK → kb_articles | Parent article |
| `version_number` | integer | Monotonic per article; unique with `article_id` |
| `title` | varchar(255) | Title at time of edit |
| `content_en` | text | English body snapshot |
| `content_ur` | text nullable | Urdu body snapshot |
| `change_summary` | varchar(512) nullable | Human-readable edit note |
| `edited_by` | varchar(128) nullable | Editor identity |
| `created_at` / `updated_at` | timestamptz | TimestampMixin (`updated_at` unused — rows are immutable) |

**Unique constraint:** `(article_id, version_number)` — prevents duplicate version numbers.

### Versioning workflow (Phase 2 services)

1. **Create** — insert article + version `1`.
2. **Edit** — update live columns on `kb_articles`, increment `current_version`, append new version row.
3. **Rollback** — load version *N*, write as version *N+1* with summary `"Rollback to vN"`, update live columns.

Bilingual RAG (Phase 2) reads `content_en` / `content_ur` based on user `language_pref`.

---

## Tables (Task 1.2.5)

ORM models: `app/db/models/webhook_event_log.py`, `app/db/models/sla_config.py`. Migrations: Task 1.2.6.

### `webhook_event_log`

| Column | Type | Description |
|--------|------|-------------|
| `id` | bigint PK | Internal id (TimestampMixin) |
| `idempotency_key` | varchar(256) unique | Dedup key from adapter (see `WEBHOOKS.md`) |
| `payload_hash` | varchar(64) | SHA-256 hex of raw webhook body |
| `event_type` | varchar(64) | `StandardEventType` value |
| `provider_event_id` | varchar(128) | Platform-native event/message id |
| `provider_ticket_id` | varchar(128) nullable | Platform conversation id |
| `status` | varchar(32) | `received`, `processed`, `duplicate`, `failed` |
| `error_message` | text nullable | Last processing error (DLQ handoff) |
| `occurred_at` | timestamptz nullable | Event time from platform payload |
| `processed_at` | timestamptz nullable | When middleware finished handling |
| `created_at` / `updated_at` | timestamptz | TimestampMixin |

**Why Postgres (not Redis only)?** Idempotency must survive restarts; audit trail for support debugging. Redis DLQ (Task 1.4) handles retry buffering only.

### `sla_config`

| Column | Type | Description |
|--------|------|-------------|
| `id` | bigint PK | Internal id |
| `plan_type` | varchar(32) unique | Matches `restaurants.plan_type` — e.g. `8h`, `16h`, `24-7` |
| `coverage_hours` | integer | Daily support window length (8, 16, or 24) |
| `first_response_minutes` | integer | Target time to first agent/AI reply |
| `resolution_minutes` | integer | Target time to resolve or escalate |
| `escalation_after_minutes` | integer | Auto-escalate if ticket open longer than this |
| `description` | varchar(512) nullable | Human-readable plan summary |
| `rules` | jsonb | Extra escalation rules (extensible without migration) |
| `is_active` | boolean | Soft-disable a plan tier |
| `created_at` / `updated_at` | timestamptz | TimestampMixin |

**Application:** Branch `timezone` (Task 1.2.2) defines *when* the coverage window applies; `sla_config` defines *how long* targets are per plan. Task 1.6 mapping loads restaurant → `plan_type` → SLA row.

Seed data: demo fixture in `scripts/fixtures/sample_tenant_export.json`; load with `scripts/seed_data.py`. Validate with `scripts/validate_seed.py`. Production export sign-off pending ButterPOS team.

---

## Relationships

See entity diagram above. Cascade: deleting a restaurant removes branches; branch delete sets user `branch_id` NULL.

---

## Customer/branch mapping chain

**Task 1.6** — implemented in `CustomerMappingService` + `CustomerMappingRepository`.

### Lookup paths

| Entry | Method | Use case |
|-------|--------|----------|
| `butterpos_user_id` | `resolve_by_user_id()` | Tablet widget / JWT `subject` |
| `provider_contact_id` | `resolve_by_contact_id()` | Chatwoot webhook sender id |

### Chain

```
users.butterpos_user_id → users.branch_id → branches → restaurants → sla_config (by plan_type)
```

### Result model

`CustomerMappingResult` (`app/models/customer_mapping.py`):

| Field | Purpose |
|-------|---------|
| `status` | `active`, `unknown_user`, `no_branch`, `payment_due`, `plan_expired`, `outside_coverage`, `sla_not_configured` |
| `max_agent_tier` | 1 (restricted) or 3 (full) — see D-15 |
| `status_message` | Human/agent-readable reason |
| `branch_timezone` | IANA tz for coverage window |
| `sla` | `SlaSnapshot` with coverage + response targets when configured |

Edge-case behavior: **D-15** in `DECISIONS.md`.

---

## Tenant export schema (Task 1.7)

Version **`1`** — JSON envelope or CSV directory. Production files come from the ButterPOS team; demo fixture: `scripts/fixtures/sample_tenant_export.json`.

### JSON envelope

```json
{
  "schema_version": "1",
  "restaurants": [ { "butterpos_restaurant_id", "name", "plan_type", "payment_due", "expiry?" } ],
  "branches": [ { "butterpos_branch_id", "butterpos_restaurant_id", "name", "timezone", "devices?" } ],
  "users": [ { "butterpos_user_id", "butterpos_branch_id?", "provider_contact_id?", "language_pref" } ],
  "sla_configs": [ { "plan_type", "coverage_hours", "first_response_minutes", "resolution_minutes", "escalation_after_minutes", "rules?", "is_active?" } ]
}
```

### CSV directory

Directory containing `restaurants.csv` (required), optional `branches.csv`, `users.csv`, `sla_configs.csv` with the same column names.

### Validation rules

| Rule | Error if violated |
|------|-------------------|
| Unique `butterpos_restaurant_id`, `butterpos_branch_id`, `butterpos_user_id` | Duplicate id |
| `plan_type` ∈ `8h`, `16h`, `24-7` | Invalid plan |
| Branch → restaurant FK by external id | Unknown restaurant |
| User → branch FK (when set) | Unknown branch |
| `timezone` valid IANA name | Invalid timezone |
| SLA rows cover all restaurant plan types (when `sla_configs` non-empty) | Missing SLA plan |

Loader: `app/services/tenant_export_loader.py`. Persistence: `app/services/tenant_seed_service.py`. CLI: `scripts/seed_data.py`.

---
