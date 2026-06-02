# Progress Checklist

Running record of completed steps. Phases are sequential — Phase 1 does not start until Phase 0 is confirmed complete here.

**Last updated:** 2026-06-01

---

## Phase 0 — Discovery & Spikes

| Step | Description | Status |
|------|-------------|--------|
| **0.0** | Pre-Phase Gate — docs scaffold + locked decisions | **Complete** |
| **0.1** | Chat surface spike (widget → middleware → Chatwoot) | **Complete** |
| **0.2** | LLM Evaluation (primary + fallback selection) | **Complete** (harness; live eval pending `OPENROUTER_API_KEY`) |
| **0.3** | KB Content Audit + MVP List | **Complete** (tooling; production audit pending WhatsApp export) |
| **0.4** | Assumption Validation (A1–A7 evidence) | **Complete** (2 verified, 2 manual, 3 blocked) |
| **0.5** | Infrastructure Setup (Docker, CI, Postgres, Redis) | **Complete** |
| **0.6** | MCP client validation + contract documentation | **Complete** (stub server; LLM loop pending API key) |

### Step 0.6 deliverables (2026-06-01)

- [x] Stub MCP server: `spikes/0.6_mcp_validation/stub_server/butterpos_stub_mcp.py`
- [x] MCP client + agent loop: `spikes/0.6_mcp_validation/client/`
- [x] Validation runner: `spikes/0.6_mcp_validation/run_validation.py`
- [x] Direct probe — all 4 tools PASS (`mcp_validation_20260601T090513Z.json`)
- [x] `MCP_INTEGRATION.md` — full contract documented
- [x] D-4 validation appendix in `DECISIONS.md`
- [x] LLM portability test — **PASS** (2026-06-02): `openai/gpt-4o-mini`, `anthropic/claude-3-haiku` via OpenRouter

**Phase 0 exit criteria:**

- [ ] Primary + fallback LLM chosen (D-9 live eval)
- [x] Chat surface validated (Step 0.1)
- [ ] Assumptions A1/A2/A3 unblocked
- [x] Staging infra up (Step 0.5 local docker-compose)
- [x] MCP contract documented (stub; swap when teammate ready)
- [x] Decisions in `DECISIONS.md`

**Phase 0 → Phase 1 gate:** Confirm with Team Lead before starting Task 1.1. Open items: D-9 (LLM eval), A1–A3 credentials, production MCP server swap, WhatsApp export (Phase 2 gate only).

**Phase 2 gate (does not block Phase 1):**

- [ ] Production KB MVP list signed off (Step 0.3 / A6)

---

## Phase 1 — Core Infrastructure

| Task | Description | Status |
|------|-------------|--------|
| 1.1 | FastAPI + `TicketingProvider` interface | Not started |
| 1.2 | PostgreSQL schema + migrations | Not started |
| 1.3 | `ChatwootAdapter` | Not started |
| 1.4 | Webhook receiver + `StandardEvent` parser | Not started |
| 1.5 | Redis cache + rate limiting | Not started |
| 1.6 | Customer/Branch mapping + unit tests (100% coverage) | Not started |
| 1.7 | Data seeding + validation | Not started |

**Phase 1 exit criteria:**

- [ ] Middleware runs
- [ ] `ChatwootAdapter` passes against local Chatwoot
- [ ] Webhooks ingest idempotently with DLQ + polling
- [ ] Caching + rate limits live
- [ ] Mapping at 100% coverage
- [ ] Data seeded and jointly validated
- [ ] Every doc current
