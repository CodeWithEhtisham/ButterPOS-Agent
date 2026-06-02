# Architecture

System design for the ButterPOS AI Support Agent middleware.

---

## Overview

The middleware sits between the **embedded tablet chat widget** and **Chatwoot**, orchestrating AI responses via **OpenRouter** (LLM) and **MCP** (diagnostic tools). It is platform-agnostic: Chatwoot is one adapter behind `TicketingProvider`; the core never imports Chatwoot directly (D-1, D-2).

```
Tablet widget → Middleware (FastAPI) → Chatwoot
                      ↓
                 OpenRouter (LLM)
                      ↓
                 MCP client → ButterPOS diagnostic tools
```

---

## Five-part architecture

1. **Embedded chat widget** — tablet UI (ButterPOS Android team)
2. **Middleware** — this repo: routing, mapping, AI loop, PII masking
3. **Chatwoot** — ticketing / conversation storage (local Docker, D-1)
4. **LLM** — OpenRouter gateway to OpenAI / Anthropic / Gemini (D-11)
5. **MCP server** — ButterPOS diagnostic tools (backend teammate)

---

## Provider isolation

| Boundary | Interface | Adapters |
|----------|-----------|----------|
| Ticketing | `TicketingProvider` | `ChatwootAdapter` (Task 1.3) |
| LLM | `LLMProvider` | `OpenRouterProvider` (spike → `app/providers/llm/`) |
| Tools | MCP client | Stub (Phase 0) → production server |

The **factory** reads `TICKETING_PROVIDER` from env and returns the correct adapter (Task 1.1.6). Swapping Chatwoot for Zoho = new adapter, zero core changes.

Configuration: `app/core/config.py` (`Settings` via pydantic-settings).

### TicketingProvider (Task 1.1.4)

Abstract interface in `app/providers/ticketing/base.py` — **12 async methods**:

| Method | Purpose |
|--------|---------|
| `create_ticket` | Open conversation for contact |
| `get_ticket` | Fetch by `provider_ticket_id` |
| `update_status` | Map `StandardStatus` transition |
| `add_comment` | Public customer-visible reply |
| `add_note` | Internal agent note |
| `assign_agent` | Assign to platform agent id |
| `add_tags` | Append labels |
| `get_or_create_contact` | Resolve/create contact |
| `verify_webhook` | HMAC / signature check |
| `parse_webhook` | Payload → `StandardEvent` |
| `health_check` | Platform API probe |
| `list_tickets_updated_since` | Polling fallback — conversations updated after timestamp |

`ChatwootAdapter` implements all methods (Task 1.3). Factory wraps with dedup + cache (Task 1.5).

### Provider factory (Task 1.1.6 + 1.5)

- Env: `TICKETING_PROVIDER` (default `chatwoot`)
- Module: `app/providers/ticketing/factory.py`
- **Chain:** `ChatwootAdapter` → `DedupingTicketingProvider` → `CachingTicketingProvider`
- FastAPI: `ticketing_provider_dep()` in `app/api/deps.py`
- Adding Zoho: implement `ZohoAdapter`, register in `_REGISTRY` — zero core changes

---

## Caching strategy

**Task 1.5.1** — Redis read-through cache on `TicketingProvider` reads.

| Cache | TTL | Keys | Invalidation |
|-------|-----|------|--------------|
| Ticket (`StandardTicket`) | 60s | `cache:ticket:{provider_ticket_id}` | Webhook for conversation; `add_comment` / `add_note`; overwritten on status/assign/tags writes |
| Contact (`StandardContact`) | 24h | `cache:contact:lookup:{uid\|email\|phone}` + `cache:contact:pid:{id}` | Webhook when sender is contact; refreshed on cache miss |

Implementation: `CachingTicketingProvider` wraps the configured adapter in `app/providers/ticketing/factory.py`. Module: `app/core/cache/ticketing_read_cache.py`.

Postgres `ticket_cache` table (Task 1.2) is the **durable mirror** for polling; Redis is the **hot read cache** for platform API calls.

## Rate limiting

**Task 1.5.2** — Redis sliding-window counters on inbound customer messages at webhook ingress.

| Limiter | Default | Module |
|---------|---------|--------|
| Per user (Chatwoot contact id) | 20 / hour | `app/core/rate_limit/inbound_message_limits.py` |
| Per restaurant (custom attribute) | 100 / day | same |

Checked in `WebhookService` after Postgres idempotency insert; duplicates do not consume quota. Over-limit webhooks ack `200 rate_limited` and skip Celery — protects LLM cost and platform API abuse without triggering Chatwoot retries.

## Request deduplication

**Task 1.5.3** — Redis layers prevent duplicate work on retried client requests and webhook replays.

| Layer | Scope | Module |
|-------|-------|--------|
| Ticket creation | `create_ticket()` when `metadata.client_request_id`, `source_id`, or `idempotency_key` is set | `DedupingTicketingProvider` in factory chain |
| Webhook hot path | `idempotency_key` before Postgres insert | `WebhookHotDedupStore` in `WebhookService` |

Postgres `webhook_event_log` remains the durable audit trail; Redis hot dedup is an optimization for platform replays within TTL.

## Inbound PII masking

**Task 1.5.3** — `InboundPiiService` masks incoming `message_body` in `process_webhook_event()` before agent/LLM paths. Tokens stored in Redis (`pii:token:{id}`) via Task 1.1.7 `PIIMasker`.

- **PII token map** — Task 1.1.7: Redis `pii:token:{id}` → original value, **24h TTL**. Used to unmask LLM responses. Invalid/expired tokens remain as placeholders in text.

---

## Customer / branch mapping

**Task 1.6** — `CustomerMappingService` resolves ButterPOS users and Chatwoot contacts to restaurant, branch, plan, and SLA context.

| Entry | Method |
|-------|--------|
| `butterpos_user_id` | `resolve_by_user_id()` |
| `provider_contact_id` | `resolve_by_contact_id()` |

Chain: `users` → `branches` → `restaurants` → `sla_config` (by `plan_type`). Evaluates `payment_due`, plan expiry, and branch timezone coverage windows.

Edge cases (`unknown_user`, `no_branch`, `payment_due`, `outside_coverage`, etc.): **D-15** in `DECISIONS.md`. **100% test coverage** required on mapping modules — see `DEV_GUIDELINES.md`.

Data loaded via Task 1.7 seed scripts; validated with `scripts/validate_seed.py`.

---

## Middleware readiness

**Task 1.8.1** — `GET /api/v1/system/health` probes Postgres (`SELECT 1`) and Redis (`PING`). Returns HTTP **503** when degraded.

Operational validation scripts (Phase 1 exit):

| Script | Purpose |
|--------|---------|
| `scripts/check_infra.py` | Direct Postgres + Redis connectivity |
| `scripts/smoke_middleware.py` | OpenAPI, health, JWT auth against running app |
| `scripts/validate_chatwoot.py` | Live `ChatwootAdapter` round-trip |
| `scripts/seed_data.py` / `scripts/validate_seed.py` | Tenant data load + mapping checks |

See `DEPLOYMENT.md` § Phase 1 verification.

---

## Agent loop

<!-- Phase 2: Playbook selection, tiered authorization, tool routing, escalation. -->
