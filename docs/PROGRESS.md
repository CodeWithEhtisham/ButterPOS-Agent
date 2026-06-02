# Progress Checklist

Running record of completed steps. Phases are sequential — Phase 1 does not start until Phase 0 is confirmed complete here.

**Last updated:** 2026-06-02

---

## Phase 0 — Discovery & Spikes

| Step | Description | Status |
|------|-------------|--------|
| **0.0** | Pre-Phase Gate — docs scaffold + locked decisions | **Complete** |
| **0.1** | Chat surface spike (widget → middleware → Chatwoot) | **Complete** |
| **0.2** | LLM Evaluation (primary + fallback selection) | **Complete** (harness; D-9 live eval optional) |
| **0.3** | KB Content Audit + MVP List | **Complete** (tooling; production audit pending WhatsApp export) |
| **0.4** | Assumption Validation (A1–A7 evidence) | **Complete** (2 verified, 2 manual, 3 blocked) |
| **0.5** | Infrastructure Setup (Docker, CI, Postgres, Redis) | **Complete** |
| **0.6** | MCP client validation + contract documentation | **Complete** |

**Phase 0 exit criteria:**

- [ ] Primary + fallback LLM chosen (D-9 live eval — optional; OpenRouter validated 2026-06-02)
- [x] Chat surface validated (Step 0.1)
- [ ] Assumptions A1/A2/A3 unblocked (deferred — does not block Task 1.1–1.5)
- [x] Staging infra up (Step 0.5 local docker-compose)
- [x] MCP contract documented (stub; swap when teammate ready)
- [x] Decisions in `DECISIONS.md`

**Phase 0 → Phase 1 gate:** **Approved** (2026-06-02) — Team Lead proceed to Phase 1 with D-9 and A1–A3 open.

**Phase 2 gate (does not block Phase 1):**

- [ ] Production KB MVP list signed off (Step 0.3 / A6)

---

## Phase 1 — Core Infrastructure

| Task | Description | Status |
|------|-------------|--------|
| **1.1** | FastAPI + `TicketingProvider` interface | **Complete** (2026-06-02) |
| **1.2** | PostgreSQL schema + migrations | **Complete** (2026-06-02) |
| **1.3** | `ChatwootAdapter` | **Complete** (2026-06-02) |
| **1.4** | Webhook receiver + `StandardEvent` parser | **Complete** (2026-06-02) |
| **1.5** | Redis cache + rate limiting | **Complete** (2026-06-02) |
| **1.6** | Customer/Branch mapping + unit tests (100% coverage) | **Complete** (2026-06-02) |
| **1.7** | Data seeding + validation | **In progress** |

### Task 1.7 sub-steps

| # | Sub-step | Status |
|---|----------|--------|
| 1 | Ingestion script — CSV/JSON validate + upsert | **Complete** (2026-06-02) |
| 2 | Joint validation with ButterPOS team | Not started |

### Task 1.5 sub-steps

| # | Sub-step | Status |
|---|----------|--------|
| 1 | Ticket cache (60s) + contact cache (24h) + webhook invalidation | **Complete** (2026-06-02) |
| 2 | Per-user + per-restaurant rate limits | **Complete** (2026-06-02) |
| 3 | Request dedup + PII token mapping | **Complete** (2026-06-02) |

### Task 1.6 sub-steps

| # | Sub-step | Status |
|---|----------|--------|
| 1 | Mapping chain + payment check + timezone | **Complete** (2026-06-02) |
| 2 | Unit tests — all scenarios + 100% coverage | **Complete** (2026-06-02) |

### Task 1.4 sub-steps

| # | Sub-step | Status |
|---|----------|--------|
| 1 | POST endpoint — verify → parse → `StandardEvent` | **Complete** (2026-06-02) |
| 2 | Idempotency + payload hashing | **Complete** (2026-06-02) |
| 3 | Dead Letter Queue (Redis + Celery) | **Complete** (2026-06-02) |
| 4 | Polling fallback (Celery beat) | **Complete** (2026-06-02) |

### Task 1.2 sub-steps

| # | Sub-step | Status |
|---|----------|--------|
| 1 | Base model (`DeclarativeBase` + `TimestampMixin`) + async session | **Complete** (2026-06-02) |
| 2 | Restaurant + Branch + User | **Complete** (2026-06-02) |
| 3 | Ticket cache + AI conversation | **Complete** (2026-06-02) |
| 4 | KB article + version history | **Complete** (2026-06-02) |
| 5 | Webhook event log + SLA config | **Complete** (2026-06-02) |
| 6 | Alembic init + first migration | **Complete** (2026-06-02) |

### Task 1.3 sub-steps

| # | Sub-step | Status |
|---|----------|--------|
| 1 | Auth — API token + async HTTP client + live health probe | **Complete** (2026-06-02) |
| 2 | `create_ticket()` | **Complete** (2026-06-02) |
| 3 | `get_ticket()` + `update_status()` + status mapping | **Complete** (2026-06-02) |
| 4 | `add_comment()` + `add_note()` | **Complete** (2026-06-02) |
| 5 | `assign_agent()` + `add_tags()` | **Complete** (2026-06-02) |
| 6 | `get_or_create_contact()` | **Complete** (2026-06-02) |
| 7 | Webhook HMAC verification + registration | **Complete** (2026-06-02) |

### Task 1.1 sub-steps

| # | Sub-step | Status |
|---|----------|--------|
| 1 | Project structure + config (`pydantic-settings`) | **Complete** (2026-06-02) |
| 2 | JWT authentication | **Complete** (2026-06-02) |
| 3 | API versioning (`/api/v1/`) | **Complete** (2026-06-02) — router wired with auth routes |
| 4 | `TicketingProvider` interface (11 methods) | **Complete** (2026-06-02) |
| 5 | Standard models (`StandardEvent`, etc.) | **Complete** (2026-06-02) |
| 6 | Provider factory | **Complete** (2026-06-02) |
| 7 | PII masking / de-masking | **Complete** (2026-06-02) |
| 8 | Structured logging + global exception handler | **Complete** (2026-06-02) |

**Phase 1 exit criteria:**

- [ ] Middleware runs
- [ ] `ChatwootAdapter` passes against local Chatwoot
- [x] Webhooks ingest idempotently with DLQ + polling
- [x] Caching + rate limits live
- [x] Mapping at 100% coverage
- [ ] Data seeded and jointly validated
- [ ] Every doc current
