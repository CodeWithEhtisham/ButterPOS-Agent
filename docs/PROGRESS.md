# Progress Checklist

Running record of completed steps. Phases are sequential — Phase 1 does not start until Phase 0 is confirmed complete here.

**Last updated:** 2026-06-01

---

## Phase 0 — Discovery & Spikes

| Step | Description | Status |
|------|-------------|--------|
| **0.0** | Pre-Phase Gate — docs scaffold + locked decisions | **Complete** |
| **0.1** | Chat surface spike (widget → middleware → Chatwoot) | **Complete** |
| **0.2** | LLM Evaluation (primary + fallback selection) | **Complete** (harness; live eval pending `OPENAI_API_KEY`) |
| **0.3** | KB Content Audit + MVP List | **Complete** (tooling; production audit pending WhatsApp export) |
| **0.4** | Assumption Validation (A1–A7 evidence) | **Complete** (2 verified, 2 manual, 3 blocked) |
| **0.5** | Infrastructure Setup (Docker, CI, Postgres, Redis) | **Complete** |
| 0.6 | MCP client validation + contract documentation | Not started |

### Step 0.5 deliverables (2026-06-01)

- [x] `docker-compose.yml` — Postgres 15 + Redis 7 with health checks
- [x] `scripts/check_infra.py` — connectivity verifier
- [x] `tests/test_infra.py` — smoke + connectivity tests
- [x] `.github/workflows/ci.yml` — ruff lint + pytest + infra check
- [x] `requirements-dev.txt`, `pyproject.toml` (ruff/pytest config)
- [x] `docs/DEPLOYMENT.md`, `docs/ENVIRONMENT.md` updated
- [x] `README.md` quick-start

**Phase 0 exit criteria (all must be checked before Phase 1):**

- [ ] Primary + fallback LLM chosen (D-9 live eval)
- [x] Chat surface validated (Step 0.1)
- [ ] Assumptions signed off — A1/A2/A3 blocked
- [x] Staging infra up (local docker-compose + CI service containers)
- [ ] MCP contract documented
- [ ] All decisions in `DECISIONS.md`

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
