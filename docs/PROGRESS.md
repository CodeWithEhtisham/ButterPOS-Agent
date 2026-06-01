# Progress Checklist

Running record of completed steps. Phases are sequential — Phase 1 does not start until Phase 0 is confirmed complete here.

**Last updated:** 2026-06-01

---

## Phase 0 — Discovery & Spikes

| Step | Description | Status |
|------|-------------|--------|
| **0.0** | Pre-Phase Gate — docs scaffold + locked decisions | **Complete** |
| **0.1** | Chat surface spike (widget → middleware → Chatwoot) | **Complete** |
| **0.2** | LLM Evaluation (primary + fallback selection) | **Complete** (harness + dataset; live eval pending `OPENAI_API_KEY`) |
| 0.3 | KB Content Audit + MVP List | Not started |
| 0.4 | Assumption Validation (A1–A7 evidence) | Not started |
| 0.5 | Infrastructure Setup (Docker, CI, Postgres, Redis) | Not started |
| 0.6 | MCP client validation + contract documentation | Not started |

### Step 0.0 deliverables (2026-06-01)

- [x] Docs scaffold created
- [x] D-1…D-6 locked ADRs written in `DECISIONS.md`
- [x] D-7 signed off (A1–A7)
- [x] D-8 recorded (OpenAI only today)

### Step 0.1 deliverables (2026-06-01)

- [x] Spike harness: `spikes/0.1_chat_surface/chat_surface_spike.py`
- [x] Capability matrix: `spikes/0.1_chat_surface/capability_matrix.md`
- [x] `WEBHOOKS.md`, `TROUBLESHOOTING.md`, `ENVIRONMENT.md` updated
- [x] Live latency run — mean 123ms, p95 176ms, all capabilities pass (`spike_report_20260601T083508Z.json`)

### Step 0.2 deliverables (2026-06-01)

- [x] 50-query dataset: `spikes/0.2_llm_eval/dataset/support_queries.json`
- [x] `LLMProvider` spike interface: `spikes/0.2_llm_eval/providers/`
- [x] Eval runner: `spikes/0.2_llm_eval/run_eval.py`
- [x] D-9 ADR stub in `DECISIONS.md`
- [x] `MCP_INTEGRATION.md` — LLM/tool-calling compatibility note
- [ ] Live scorecard + primary/fallback — **blocked:** add `OPENAI_API_KEY` to `.env` and run eval

**Phase 0 exit criteria (all must be checked before Phase 1):**

- [ ] Primary + fallback LLM chosen (D-9 live eval)
- [x] Chat surface validated (Step 0.1 live run)
- [ ] Assumptions signed off with evidence (Step 0.4)
- [ ] Staging environment up
- [ ] MCP contract documented
- [ ] All decisions in `DECISIONS.md`

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
