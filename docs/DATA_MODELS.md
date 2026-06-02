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

## Tables

<!-- Task 1.2: Restaurant, Branch, User, Ticket Cache, AI Conversation, KB Article, Webhook Event Log, SLA Config. -->

---

## Relationships

<!-- Task 1.2: Entity relationship diagram and foreign keys. -->

---

## Customer/branch mapping chain

<!-- Task 1.6: User ID → restaurant → branch → plan; payment_due; timezone resolution. -->
