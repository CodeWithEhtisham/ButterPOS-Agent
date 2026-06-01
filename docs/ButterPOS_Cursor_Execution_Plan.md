# ButterPOS AI Support Agent — Cursor Execution Plan (Phase 0 & Phase 1)

**Owner:** Ehtisham Ahmed · **LLM (V1):** paid cloud providers — OpenAI / Gemini / Anthropic (any), behind an `LLMProvider` interface · **Local LLM (Ollama):** deferred, not in V1 · **Ticketing platform:** Chatwoot (running locally via Docker — team decision, tested vs Zoho) · **Tool calling:** MCP (team decision, tested vs direct calling) · **MCP server:** owned by backend teammate

> **Locked team decisions (already made — Cursor does not re-litigate these):** Chatwoot, not Zoho (free + local). MCP, not direct tool calling. Paid cloud LLMs only for now (no local). The Phase 0 spikes for these became *validation + documentation*, not open bake-offs — see Section 3.

This document is the single source of truth for how Cursor builds this project. It has two halves:

1. **The Operating Contract** — paste this into a Cursor rule (`.cursor/rules/00-execution-contract.mdc`, `alwaysApply: true`). It forces Cursor to work phase-by-phase, explain itself, ask before proceeding, and document as it goes.
2. **The Execution Plan** — Phase 0 and Phase 1 broken into gated steps. Keep this as `docs/EXECUTION_PLAN.md` in the repo. Cursor reads it to know *what* to build next; the contract governs *how*.

---

## 0. How to drive this with Cursor

### 0.1 One-time setup

```
your-repo/
├── .cursor/
│   └── rules/
│       ├── 00-execution-contract.mdc   # alwaysApply: true  (Section 1 below)
│       └── 10-coding-standards.mdc      # alwaysApply: true  (Section 1.4 below)
├── docs/
│   ├── EXECUTION_PLAN.md                # this file
│   ├── ARCHITECTURE.md
│   ├── API_SPEC.md
│   ├── WEBHOOKS.md
│   ├── MCP_INTEGRATION.md
│   ├── DATA_MODELS.md
│   ├── AUTH.md
│   ├── ENVIRONMENT.md
│   ├── DEPLOYMENT.md
│   ├── DEV_GUIDELINES.md
│   ├── TROUBLESHOOTING.md
│   ├── DECISIONS.md                     # ADR log — every architectural choice + why
│   └── PROGRESS.md                      # running checklist of completed steps
```

`.mdc` rule files use YAML frontmatter. The contract rule starts with:

```
---
description: ButterPOS phased execution contract — governs how every task is built
globs: ["**/*"]
alwaysApply: true
---
```

(`.cursorrules` at repo root still works if your Cursor version doesn't pick up the folder, but it's the legacy path — prefer `.cursor/rules/`.)

### 0.2 The kickoff prompt (paste into Cursor chat to start)

> Read `docs/EXECUTION_PLAN.md` and follow `.cursor/rules/00-execution-contract.mdc`. We are starting **Phase 0, Pre-Phase Gate**. Do not write any production code yet. First, restate the open decisions you need from me (the D-items in the plan), then propose the docs scaffold. Stop and wait for my confirmation.

### 0.3 The loop you'll repeat for every step

1. You say: *"Proceed with [step ID]."*
2. Cursor states the **goal**, **what it's about to do**, and **why**.
3. Cursor asks for any **missing inputs** (credentials, decisions, config) — and stops if blocked.
4. Cursor implements **only that step**.
5. Cursor updates the **relevant doc(s)** and `PROGRESS.md`.
6. Cursor gives you a **"be ready to explain"** summary (the 2–3 things your Team Lead might ask about this step).
7. Cursor **stops at the gate** and asks for confirmation before the next step.

---

## 1. The Operating Contract (copy into `00-execution-contract.mdc`)

> You are the implementation agent for the ButterPOS AI Support Agent. You follow this contract on every turn, without exception.

### 1.1 Phase and step gating
- Work **one step at a time**. Never implement a whole task or phase in a single pass.
- After completing a step, **stop** and wait for explicit confirmation ("proceed", "next", or a step ID) before starting the next.
- Never silently skip a step or merge steps. If a step is unnecessary, say so and ask permission to skip.
- Phases are sequential: do not start Phase 1 until Phase 0 is confirmed complete in `PROGRESS.md`.

### 1.2 Explain-then-do
- Before writing code for any step, state in 2–4 sentences: **the goal**, **what you will change/create**, and **why this approach** over the obvious alternatives.
- Surface trade-offs. If a decision is being made, log it in `docs/DECISIONS.md` as a short ADR (context → decision → consequences) before moving on.

### 1.3 Ask, don't assume
- If you need a credential, env value, API detail, business rule, or architectural decision and don't have it, **ask and stop**. Do not invent placeholders that look real (no fake client IDs, no guessed schema fields).
- Where a real secret is required, instruct the user to add it to `.env` themselves and reference it by name only. Never print or commit secrets.
- If the plan and the running code disagree, stop and flag the conflict — do not "fix" it unilaterally.

### 1.4 Document as you go (this is a hard gate, not optional)
Every step must update the relevant doc(s) **before** the confirmation gate:
- New endpoint → `API_SPEC.md`
- New/changed webhook → `WEBHOOKS.md`
- MCP client/tool change → `MCP_INTEGRATION.md`
- New table/model/relationship → `DATA_MODELS.md`
- Auth/token/permission change → `AUTH.md`
- New env var → `ENVIRONMENT.md`
- Deploy/infra change → `DEPLOYMENT.md`
- Any architectural choice → `DECISIONS.md`
- Any recurring failure + fix → `TROUBLESHOOTING.md`
- Always tick the step in `PROGRESS.md`.

Docs are written so a new engineer (or the Team Lead) can understand the system without reading code.

### 1.5 Coding standards (can live in `10-coding-standards.mdc`)
- Python 3.11+, FastAPI, async-first. Type hints on every function. Pydantic v2 for all models.
- No business logic in route handlers — routes call services. Services are testable in isolation.
- **Provider isolation:** the middleware core NEVER imports Chatwoot (or any platform) directly. All platform calls go through the `TicketingProvider` interface. Same rule for the LLM: the core talks to an `LLMProvider` interface, never to `openai` directly (see D-3).
- All external calls (platform API, LLM API, MCP) are wrapped with timeout, retry, and structured logging.
- Secrets only from env via `pydantic-settings`. Never hardcoded.
- Every new module ships with tests. Customer/branch mapping logic requires 100% coverage (per Phase 1 Task 6).

### 1.6 Be ready to explain
At the end of each step, give a short **"Team Lead Q&A"** block: the 2–3 questions most likely to be asked about what was just built, with one-line answers. This is so the human owner can defend every decision.

---

## 2. Project context Cursor must hold in mind

**What it is:** An autonomous support agent embedded in the ButterPOS tablet app. It diagnoses, fixes, and verifies common POS issues (sync stuck, printer offline, cache, login loop), and escalates novel cases to a human. Most tickets = 2–4 diagnostic checks + one of <20 known fixes.

**The five-part architecture:** embedded chat widget (thin) → **middleware** (the brain: owns ticket state, runs the agent loop, calls the LLM, calls the platform, routes tool calls) → **Chatwoot** (system of record, not the runtime) → **LLM** (reasoning) → **MCP diagnostic layer** (tools on local server + tablet). The reasoning layer never touches a device directly; the middleware's routing layer does.

**Non-negotiable principles:**
- **Platform-agnostic core** behind `TicketingProvider`. Chatwoot is one adapter.
- **Tiered authorization:** Tier 1 read-only auto; Tier 2 fix on high-confidence / soft-confirm otherwise; Tier 3 always escalate.
- **PII masking is load-bearing right now.** Because V1 routes through paid cloud LLM providers (OpenAI / Gemini / Anthropic), customer PII *does* leave your infrastructure unless masked — and it could go to any of three vendors. The "self-hosted = PII never leaves" advantage from the proposal does **not** apply yet. Masking before every LLM call is mandatory, not nice-to-have. Revisit when Ollama lands.
- **Playbooks over freeform reasoning:** the LLM selects from pre-vetted symptom→fix playbooks.

**The MCP boundary:** Your backend teammate owns the MCP server (it knows the existing ButterPOS models, APIs, and business logic). Your middleware is the **MCP client**. You do not build the server. You define and document the **contract** you depend on (tool names, inputs, outputs, auth) in `MCP_INTEGRATION.md` and keep it in sync with your teammate.

**The "Super Agent" goal:** beyond diagnostics, the agent will create/update/fix/manage tasks across the platform via MCP tools. So the tool-calling layer must be extensible from day one — adding a tool should not require touching the agent loop.

---

## 3. Decisions to resolve at the very start (the Pre-Phase Gate)

Most of these are now **locked team decisions** — Cursor confirms them into `DECISIONS.md` with the rationale (so the choices are documented for the Team Lead) but does **not** re-open them. Only the items marked *OPEN* still need your input.

| ID | Decision | Status | Why it matters |
|----|----------|--------|----------------|
| **D-1** | Ticketing platform for V1 | **LOCKED → Chatwoot.** Team tested Zoho vs Chatwoot; chose Chatwoot (free, runs locally). Zoho is out of V1. | Task 3 is `ChatwootAdapter` (API key + HMAC webhooks), not `ZohoAdapter`/OAuth. No Zoho SDK spike. Interface keeps Zoho addable later. |
| **D-2** | Chat surface for V1 | **LOCKED → widget → middleware → Chatwoot** (not widget → Chatwoot direct). Zoho ASAP SDK dropped. | Phase 0 Task 1 becomes a Chatwoot API-channel capability + latency spike. |
| **D-3** | LLM abstraction | **LOCKED → `LLMProvider` interface, now core (not optional).** V1 runs across multiple paid providers (OpenAI / Gemini / Anthropic). | With 3 vendors in play and swapping likely, the core must never import a vendor SDK. Same pattern as `TicketingProvider`. Ollama later = one more adapter. |
| **D-4** | MCP vs custom tool-calling | **LOCKED → MCP.** Team tested both; chose MCP. | Phase 0 POC becomes "confirm the MCP client works across the paid LLMs + document why MCP won" — not a bake-off. No custom path built. |
| **D-5** | Roman Urdu quality bar | **LOCKED → board target:** Roman Urdu ≥75% acceptable, latency <8s, plus cost/1K tokens. | Drives primary/fallback selection across OpenAI/Gemini/Anthropic in Phase 0. |
| **D-6** | LLM provider set for V1 | **LOCKED → paid cloud only:** OpenAI, Gemini, Anthropic. Self-hosted Llama/Ollama **deferred** (not cancelled). | Step 0.2 evaluates the paid providers to pick **primary + fallback**. Local revisited post-V1. |
| **D-7** | Assumptions A1–A7 | *OPEN* — re-mapped to Chatwoot; still need sign-off (app codebase access, data structure, billing source, team split). | Phase 0 Assumption Validation gate. |
| **D-8** | Which paid providers do you have keys for *today*? | *OPEN* — need from you. | Step 0.2 can only score providers you can authenticate; the rest are noted as "to test when key available." |

> **Cursor's first action:** write the LOCKED decisions (D-1…D-6) into `DECISIONS.md` with their rationale, then ask the user only the OPEN items (D-7 sign-off, D-8 which keys you have). Do not re-open locked decisions.

---

## 4. PHASE 0 — Discovery & Spikes (target ~7 working days)

**Purpose:** validate every unknown before production code. Nothing here is throwaway-quality, but nothing here is the final system either — these are spikes that produce **decisions + documented evidence**.

### Step 0.0 — Pre-Phase Gate
- **Goal:** lock the D-1…D-7 decisions and scaffold `docs/`.
- **Cursor does:** create the docs scaffold (empty files with section headers), write D-answers into `DECISIONS.md`.
- **Ask for:** answers to the decision table.
- **Deliverable:** populated `DECISIONS.md`, empty doc scaffold.
- **Gate:** confirm decisions before any spike.

### Step 0.1 — Chat surface spike *(replaces "SDK Spike + Zoho Load Test")*
- **Goal:** prove the widget→middleware→Chatwoot path supports what you need: posting messages, buttons/quick-replies/inline rating, and acceptable refresh latency (**<5s** target from the board).
- **Cursor does:** a minimal test harness that posts a message through a stub middleware into your local Chatwoot, reads it back, and measures round-trip latency. Document which rich-UI elements (buttons, quick replies, CSAT) are feasible via the API channel.
- **Ask for:** local Chatwoot base URL, API access token, account/inbox IDs.
- **Deliverable:** latency numbers + a pass/fail capability table.
- **Docs:** `WEBHOOKS.md` (Chatwoot inbound shape), `TROUBLESHOOTING.md` (any Chatwoot quirks).
- **Be ready to explain:** why widget→middleware→Chatwoot (not widget→Chatwoot direct): latency, rich UI control, decoupling agent uptime from Chatwoot.

### Step 0.2 — LLM Evaluation
- **Goal:** pick a **primary + fallback** model on real data.
- **Cursor does:**
  1. Build the **50+ query dataset** (15 English, 15 Roman Urdu, 10 code-switched, 5 short/vague, 5 multi-step) as JSON/CSV.
  2. Build a runner — calling through the **`LLMProvider` interface** (D-3), so adding a provider is config, not new plumbing — that sends every query through each candidate and logs response, latency, token count, cost.
  3. Candidates: the paid providers you have keys for — **OpenAI (e.g. GPT-4o / 4o-mini), Google Gemini, Anthropic Claude**. Score whichever you can authenticate today (D-8); note the rest as "test when key available." Llama/Ollama skipped (D-6).
  4. Score against D-5 bar: Roman Urdu ≥75%, latency <8s, cost/1K tokens.
- **Ask for:** which provider keys you have (D-8 — only test what you can authenticate); the real support-query examples if you have them.
- **Deliverable:** a scoring table across providers + chosen **primary + fallback**.
- **Docs:** `DECISIONS.md` (model choice + numbers), `MCP_INTEGRATION.md` (note: tool-calling must work for whichever providers you pick).
- **Be ready to explain:** why this model won the primary slot and which is fallback — the latency/quality/cost trade — and that the `LLMProvider` interface means swapping or adding a provider needs no core changes.

### Step 0.3 — KB Content Audit + MVP List *(hard gate for Phase 2 — do it, but it doesn't block Phase 1)*
- **Goal:** turn 3–6 months of WhatsApp support history into the **top-30 article MVP list**.
- **Cursor does:** a categorizer (billing, printer, crash, login, menu, network) that counts frequency; then a 30-row spreadsheet template (issue title, category, frequency, existing doc Y/N, author, Roman-Urdu-needed Y/N).
- **Ask for:** the WhatsApp export (or a sample), and who the article authors are.
- **Deliverable:** frequency report + 30-article MVP sheet with owners.
- **Docs:** note in `DECISIONS.md` that this gates Phase 2 KB work.

### Step 0.4 — Assumption Validation (A1–A7)
- **Goal:** definitive Yes/No on every assumption, re-mapped per D-1/D-7.
- **Cursor does:** produce a checklist and, where it can, a tiny script to verify (e.g. confirm restaurant/branch/plan rows exist; identify the billing/payment API).
- **Ask for:** Chatwoot credentials, ButterPOS Android repo access, DB connection/read access, billing source.
- **Deliverable:** signed-off assumption checklist.
- **Docs:** `DECISIONS.md`, `ENVIRONMENT.md` (where each credential lives).

### Step 0.5 — Infrastructure Setup
- **Goal:** a working staging environment.
- **Cursor does:** Ubuntu 22.04+ server prep notes; Docker + Compose v2; PostgreSQL 15 + Redis 7 containers via `docker-compose`; GitHub repo skeleton (`.gitignore`, `README`, GitHub Actions: build + lint + test on push).
- **Ask for:** server target (internal vs VPS) + SSH access, GitHub org/repo name.
- **Deliverable:** `docker-compose.yml`, CI workflow, reachable Postgres + Redis.
- **Docs:** `DEPLOYMENT.md`, `ENVIRONMENT.md`.
- **Be ready to explain:** why Postgres + Redis (state/audit vs cache/locks/rate-limits/queue), and what the CI gates on.

### Step 0.6 — MCP client validation *(decision locked per D-4 — this is confirmation + documentation, not a bake-off)*
- **Goal:** the team already chose MCP over direct tool calling. This step proves your middleware works as an **MCP client**, that tool calls fire across your paid providers (OpenAI / Gemini / Anthropic), and captures *why MCP won* for the record.
- **Cursor does:** connect the middleware (as MCP client) to your teammate's MCP server (or a stub exposing `get_system_info`, `check_printer`, `add_menu_item`, `get_sales`); call the tools through the `LLMProvider` interface with one provider; then re-point to a second provider and confirm the **same tools fire with no code change** — the portability that justified the MCP decision.
- **Ask for:** from your teammate — the MCP server URL/transport, tool list, auth method, and example tool schemas (this is the contract you'll document).
- **Deliverable:** working tool calls across ≥2 providers + the documented MCP contract + a short "why MCP beat direct calling" note.
- **Docs:** `MCP_INTEGRATION.md` (transport, auth, tool catalog, request/response shapes, ownership split), `DECISIONS.md` (the MCP rationale).
- **Be ready to explain:** the client/server split (teammate owns the server; you own the client + contract) and the concrete reason MCP won — tool portability across providers with zero per-model rewrites.

**Phase 0 exit criteria:** primary+fallback LLM chosen; chat surface validated; assumptions signed off; staging up; MCP contract documented; all decisions in `DECISIONS.md`. Cursor confirms in `PROGRESS.md` and **stops** before Phase 1.

---

## 5. PHASE 1 — Core Infrastructure (target ~14 working days)

**Purpose:** the platform-agnostic middleware backbone, with Chatwoot as a replaceable adapter behind `TicketingProvider`. Built test-first where the board demands coverage.

### Task 1.1 — FastAPI + `TicketingProvider` interface
Build in this sub-step order, gating after each:

1. **Project structure + config** — folder layout, `pydantic-settings` loading `.env`. *Docs: `ENVIRONMENT.md`, `DEV_GUIDELINES.md`.*
2. **JWT authentication** — token create/validate, FastAPI dependencies for protected routes. *Docs: `AUTH.md`.*
3. **API versioning** — everything under `/api/v1/`. *Docs: `API_SPEC.md`.*
4. **`TicketingProvider` abstract interface (11 methods)** — `create_ticket, get_ticket, update_status, add_comment, add_note, assign_agent, add_tags, get_or_create_contact, verify_webhook, parse_webhook, health_check`. *Docs: `ARCHITECTURE.md` (the abstraction), `API_SPEC.md`.*
5. **Standard models** — `StandardEvent`, `StandardStatus` (12-value enum), `StandardTicket`, `StandardEventType` (Pydantic). *Docs: `DATA_MODELS.md`.*
6. **Provider factory** — reads `TICKETING_PROVIDER` env var, imports the right adapter. *Docs: `ARCHITECTURE.md`, `ENVIRONMENT.md`.*
7. **PII masking / de-masking layer** — detect & mask phone, email, financial, ID, name **before LLM**; reversible via Redis mapping (24h TTL). *Docs: `AUTH.md` or a dedicated PII section; flag the OpenAI-API implication.*
8. **Structured logging + global exception handler** — every request logged with timestamp, `user_id`, `ticket_id`. *Docs: `DEV_GUIDELINES.md`, `TROUBLESHOOTING.md`.*

- **Be ready to explain:** why the core never imports the platform; how the factory swaps providers; why PII masking is mandatory *today* given the ChatGPT API.

### Task 1.2 — PostgreSQL schema + migrations
Sub-steps (gate after each migration):
1. **Base model** — SQLAlchemy `DeclarativeBase` + `TimestampMixin` (`id, created_at, updated_at`).
2. **Restaurant + Branch + User** — Restaurant(`plan_type, payment_due, expiry`); Branch(`timezone, devices`); User(`provider_contact_id, language_pref`). Note `provider_contact_id` keeps it platform-agnostic.
3. **Ticket Cache + AI Conversation** — ticket cache (platform-agnostic mirror); AI conversation (`messages_json` JSONB, `confidence_history`).
4. **KB Article + Version History** — versioned, bilingual (`content_ur`), full edit history for rollback.
5. **Webhook Event Log + SLA Config** — webhook idempotency (unique key); SLA escalation rules per plan type.
6. **Alembic init + first migration** — async engine, generate initial migration.
- *Docs: `DATA_MODELS.md` (every table + relationships + why platform-agnostic).* 
- **Be ready to explain:** why `provider_contact_id` instead of a Chatwoot/Zoho-specific ID; why a local ticket cache mirror exists at all.

### Task 1.3 — `ChatwootAdapter` *(was ZohoAdapter — per D-1)*
Implements `TicketingProvider`; all Chatwoot specifics live here; **the middleware never imports Chatwoot directly.**
1. **Auth** — Chatwoot API access token (from env/Redis). *(If D-1 were overridden back to Zoho, this becomes OAuth 2.0 refresh-token management instead — note the divergence in DECISIONS.md.)*
2. **`create_ticket()`** — map create payload → Chatwoot conversation/contact → return `StandardTicket`.
3. **`get_ticket()` + `update_status()`** — fetch + map to `StandardTicket`; map `StandardStatus` ↔ Chatwoot statuses.
4. **`add_public_comment()` + `add_internal_note()`** — AI reply as public message; handoff summary as private note.
5. **`assign_agent()` + `add_tags()`** — assign to agent/team; add AI classification labels.
6. **`get_or_create_contact()`** — map user → Chatwoot contact, create if absent.
7. **Webhook registration + signature verification** — register webhook URL; **HMAC** verification on inbound (Chatwoot), not Zoho's scheme.
- *Docs: `API_SPEC.md` (the mappings), `WEBHOOKS.md` (HMAC verification), `AUTH.md`.*
- **Be ready to explain:** the Status enum mapping table; why HMAC (and where the signing secret lives); how a future ZohoAdapter would slot in unchanged behind the interface.

### Task 1.4 — Webhook receiver + `StandardEvent` parser
1. **POST endpoint** — receives raw webhook → `adapter.verify_webhook()` → `adapter.parse_webhook()` → `StandardEvent`.
2. **Idempotency + payload hashing** — unique key per event, SHA-256 of payload, skip duplicates.
3. **Dead Letter Queue** — failed webhooks → Redis DLQ; Celery retries every 5 min, max 3, alert after 3 failures.
4. **Polling fallback** — Celery beat queries the platform every 10 min, reconciles with local cache.
- *Docs: `WEBHOOKS.md` (full lifecycle, idempotency, DLQ, polling), `TROUBLESHOOTING.md`.*
- **Be ready to explain:** why idempotency (platforms resend), why a DLQ *and* polling (webhooks get dropped — defense in depth).

### Task 1.5 — Redis cache + rate limiting
1. **Ticket cache (60s TTL) + contact cache (24h)** — cache reads to cut API calls; invalidate on webhook.
2. **Per-user + per-restaurant rate limits** — sliding window; 20 msgs/hr per user, 100/day per restaurant.
3. **Request dedup + PII token mapping** — prevent double-tap ticket creation; store reversible PII masks (ties into Task 1.1.7).
- *Docs: `ARCHITECTURE.md` (caching strategy), `AUTH.md`/PII section, `ENVIRONMENT.md`.*
- **Be ready to explain:** cache invalidation strategy (webhook-driven), and why rate limits protect both cost and the platform API.

### Task 1.6 — Customer/Branch mapping + unit tests *(100% coverage required)*
1. **Mapping chain + payment check + timezone** — User ID → restaurant → branch → plan; check `payment_due`; resolve branch timezone.
2. **Unit tests: all scenarios + edge cases** — active plan, expired, unpaid, 8h/16h/24-7 hours, unknown user, no branch.
- *Docs: `DATA_MODELS.md` (the chain), `DEV_GUIDELINES.md` (coverage rule).*
- **Be ready to explain:** every edge case and what the agent does in each (e.g. unpaid → behavior?). This is the board's hard 100%-coverage gate — Cursor must show coverage output.

### Task 1.7 — Data seeding + validation
1. **Ingestion script** — reads CSV/JSON export, validates, inserts into Postgres.
2. **Joint validation with ButterPOS team** — both teams verify loaded data; sign off.
- **Ask for:** the data export from the ButterPOS team and the agreed schema.
- *Docs: `DEPLOYMENT.md` (how to seed), `DATA_MODELS.md` (validation rules).*
- **Be ready to explain:** validation rules and what "signed off" means (who verified what).

**Phase 1 exit criteria:** middleware runs; `ChatwootAdapter` passes against your local Chatwoot; webhooks ingest idempotently with DLQ + polling; caching + rate limits live; mapping at 100% coverage; data seeded and jointly validated; every doc current. Confirm in `PROGRESS.md`.

---

## 6. Quick reference — what stays, changes, drops vs the boards

| Board item | Status in this plan | Reason |
|------------|---------------------|--------|
| SDK Spike + Zoho Load Test | **Replaced** with Chatwoot chat-surface spike | D-1/D-2: team chose Chatwoot (free + local) |
| Test Llama 3.1 (if GPU) | **Deferred** (V1 = paid cloud only) | D-6: no local LLM in V1 |
| MCP vs Custom POC | **Decided → MCP** (validation + docs only) | D-4: team chose MCP after testing both |
| ZohoAdapter (Task 3) | **Becomes `ChatwootAdapter`** | D-1 |
| OAuth 2.0 token mgmt | **Becomes API-key + HMAC** | Chatwoot auth model |
| `LLMProvider` interface | **Added, now core** | D-3: multiple paid providers (OpenAI/Gemini/Anthropic) in V1 + clean Ollama path later |
| LLM eval (single model) | **Across OpenAI / Gemini / Anthropic** to pick primary + fallback | D-6: any paid provider allowed |
| Everything else | **Kept as-is** | Boards are sound |

---

*Prepared as a Cursor-ready execution plan for the ButterPOS AI Support Agent. Keep `DECISIONS.md` as the living record — when the Team Lead asks "why did you do X," the answer should already be written there.*
