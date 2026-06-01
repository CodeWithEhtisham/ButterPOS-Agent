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
| 0.4 | Assumption Validation (A1–A7 evidence) | Not started |
| 0.5 | Infrastructure Setup (Docker, CI, Postgres, Redis) | Not started |
| 0.6 | MCP client validation + contract documentation | Not started |

### Step 0.0 deliverables (2026-06-01)

- [x] Docs scaffold created
- [x] D-1…D-6 locked ADRs written in `DECISIONS.md`
- [x] D-7 signed off (A1–A7)
- [x] D-8 recorded (OpenAI only today)

### Step 0.1 deliverables (2026-06-01)

- [x] Spike harness + capability matrix
- [x] Live latency run — mean 123ms, p95 176ms, all capabilities pass

### Step 0.2 deliverables (2026-06-01)

- [x] 50-query dataset + `LLMProvider` spike + eval runner
- [ ] Live scorecard + primary/fallback (D-9) — pending `OPENAI_API_KEY`

### Step 0.3 deliverables (2026-06-01)

- [x] Categorizer + MVP generator: `spikes/0.3_kb_audit/run_audit.py`
- [x] 30-row CSV template: `spikes/0.3_kb_audit/templates/mvp_articles_template.csv`
- [x] D-10 ADR — KB MVP gates Phase 2 (`DECISIONS.md`)
- [x] Demo run on sample data (categorizer validated)
- [ ] Production frequency report + signed-off MVP list — **pending WhatsApp export + article authors**

**Phase 0 exit criteria (all must be checked before Phase 1):**

- [ ] Primary + fallback LLM chosen (D-9 live eval)
- [x] Chat surface validated (Step 0.1)
- [ ] Assumptions signed off with evidence (Step 0.4)
- [ ] Staging environment up
- [ ] MCP contract documented
- [ ] All decisions in `DECISIONS.md`

**Phase 2 gate (does not block Phase 1):**

- [ ] Production KB MVP list signed off (Step 0.3)

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
