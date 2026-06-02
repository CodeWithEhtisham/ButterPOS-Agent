# Architectural Decision Records (ADR)

Living record of every architectural choice and why it was made. When the Team Lead asks "why did you do X," the answer should already be here.

---

## ADR Index

| ID | Title | Status |
|----|-------|--------|
| D-1 | Ticketing platform: Chatwoot (not Zoho) | Locked |
| D-2 | Chat surface: widget → middleware → Chatwoot | Locked |
| D-3 | LLM abstraction: `LLMProvider` interface | Locked |
| D-4 | Tool calling: MCP (not direct/custom) | Locked |
| D-5 | Roman Urdu quality bar | Locked |
| D-6 | LLM provider set: paid cloud only; Ollama deferred | Locked |
| D-7 | Assumptions A1–A7 | Resolved (2026-06-01) |
| D-8 | Provider API keys available today | Superseded by D-11 (2026-06-01) |
| D-9 | Primary + fallback LLM model | Pending (Step 0.2 — live eval blocked on `OPENROUTER_API_KEY`) |
| D-10 | KB MVP list gates Phase 2 | Resolved (2026-06-01) — production audit pending WhatsApp export |
| D-11 | LLM gateway: OpenRouter | Locked (2026-06-01) |

---

## D-1 — Ticketing platform: Chatwoot (not Zoho)

**Status:** Locked

### Context

V1 needs a ticketing system of record for support conversations, agent handoff, and audit trails. The team evaluated Zoho Desk vs Chatwoot for cost, local deployment, and integration fit.

### Decision

Use **Chatwoot** for V1 — free, runs locally via Docker. Zoho is out of V1 scope.

### Consequences

- Phase 1 builds `ChatwootAdapter` (API access token + HMAC webhooks), not `ZohoAdapter`/OAuth.
- The middleware core never imports Chatwoot directly; all platform calls go through the `TicketingProvider` interface.
- A future `ZohoAdapter` can slot in with zero core changes.
- **Legacy note:** The repo currently contains `app/core/ticketing/adapters/zoho/` from pre-decision work. Replacement with `ChatwootAdapter` is Phase 1 scope.

---

## D-2 — Chat surface: widget → middleware → Chatwoot

**Status:** Locked

### Context

The embedded tablet chat widget must support rich UI (buttons, quick replies, CSAT), acceptable latency, and decoupling of agent uptime from Chatwoot availability. A direct widget→Chatwoot path was considered (including Zoho ASAP SDK).

### Decision

All chat traffic routes **widget → middleware → Chatwoot**. No direct widget→Chatwoot path. Zoho ASAP SDK dropped.

### Consequences

- Phase 0 Step 0.1 validates Chatwoot API-channel capabilities and round-trip latency (<5s target).
- Middleware owns the agent loop, LLM calls, platform calls, and tool routing.
- Rich UI elements are mediated by middleware, giving full control over rendering and fallback behavior.

---

## D-3 — LLM abstraction: `LLMProvider` interface (core, not optional)

**Status:** Locked

### Context

V1 may use OpenAI, Google Gemini, or Anthropic Claude. Provider swapping is likely during evaluation and operations. Self-hosted Ollama is deferred but not cancelled. Without an abstraction, the core would accumulate vendor-specific SDK imports and branching logic.

### Decision

The core **never** imports vendor LLM SDKs (`openai`, `google-generativeai`, `anthropic`). All model calls go through an **`LLMProvider`** interface — the same isolation pattern as `TicketingProvider`.

### Consequences

- Step 0.2 eval runner calls through `LLMProvider`; adding or swapping a provider is config, not new plumbing.
- Adding Ollama post-V1 = one adapter + config change, no core rewrite.
- Tool-calling behavior must work consistently across whichever providers are selected.

---

## D-4 — Tool calling: MCP (not direct/custom)

**Status:** Locked

### Context

The agent needs diagnostic and operational tools (system info, printer checks, menu updates, sales queries). The team tested MCP (Model Context Protocol) vs direct/custom tool-calling implementations.

### Decision

Use **MCP**. The backend teammate owns the MCP server (ButterPOS models, APIs, business logic). This middleware is the **MCP client** only.

### Consequences

- Phase 0 Step 0.6 is validation + contract documentation, not a bake-off.
- Tool catalog, transport, auth, and request/response shapes live in `MCP_INTEGRATION.md`.
- The agent loop must stay extensible — adding a new tool must not require touching the loop.
- MCP portability across LLM providers (same tools fire with no code change when re-pointing providers) was a key factor in the decision.

### Step 0.6 validation (2026-06-01)

**Stub server:** `spikes/0.6_mcp_validation/stub_server/butterpos_stub_mcp.py` (placeholder until backend teammate ships production server).

| Check | Result |
|-------|--------|
| MCP client connects (stdio) | Validated |
| `list_tools` — 4 tools discovered | Validated |
| Direct `call_tool` probe | **Pass** (2026-06-01) |
| LLM + MCP agent loop | **Pass** (2026-06-02) — `openai/gpt-4o-mini`, `anthropic/claude-3-haiku` via OpenRouter |

**Why MCP beat direct calling (evidence):**

1. Tool definitions live on MCP server; client calls `list_tools` — no hardcoded function schemas in middleware
2. LLM receives tools via OpenAI-compatible `tools[]` converted from MCP catalog — swap model slug = config change only (D-11)
3. Backend teammate can add POS tools without middleware deploy (contract sync only)
4. Direct calling would duplicate schemas per LLM vendor and couple middleware to ButterPOS APIs

Replace stub with production server via `MCP_SERVER_URL` / stdio command — client + agent loop unchanged.

---

## D-5 — Roman Urdu quality bar

**Status:** Locked

### Context

The primary ButterPOS user base communicates in Roman Urdu. The board set measurable quality targets to drive LLM provider selection and acceptance criteria.

### Decision

- Roman Urdu: **≥75%** acceptable responses
- Latency: **<8s** per query
- Cost: track **cost per 1K tokens**

### Consequences

- Step 0.2 scoring weights quality, latency, and cost when picking primary + fallback models.
- KB content and playbooks must account for bilingual (English + Roman Urdu) support.
- Models that fail the Roman Urdu bar cannot be primary, regardless of English performance.

---

## D-6 — LLM provider set: paid cloud only; Ollama deferred

**Status:** Locked

### Context

Self-hosted Llama/Ollama was considered for PII containment and cost control. However, V1 prioritizes time-to-market, model quality (especially Roman Urdu), and operational simplicity. Paid cloud providers offer stronger multilingual performance today.

### Decision

V1 candidates: **OpenAI**, **Google Gemini**, **Anthropic Claude**. Self-hosted Llama/Ollama is **deferred** (not cancelled).

### Consequences

- Step 0.2 evaluates paid providers only; Ollama/Llama skipped per this decision.
- **PII masking before every LLM call is mandatory** — V1 sends data to third-party paid providers. The "self-hosted = PII never leaves" advantage does not apply yet. Revisit masking policy when Ollama lands.
- Step 0.2 picks a **primary + fallback** from evaluated providers.

---

## D-7 — Assumptions A1–A7

**Status:** Resolved (2026-06-01) — signed off by project owner

### Context

Phase 0 requires explicit sign-off on foundational assumptions before spikes and production work. Assumptions were re-mapped after D-1 (Chatwoot) and D-2 (middleware chat path) were locked.

### Decision

Initial sign-off (2026-06-01). **Step 0.4 validation** (2026-06-01) adds evidence per assumption:

| ID | Assumption | Validation status | Evidence |
|----|------------|-------------------|----------|
| A1 | Android/tablet app codebase access | **Blocked** | `BUTTERPOS_ANDROID_REPO` not set — need git URL or local path |
| A2 | Restaurant → Branch → User data accessible | **Blocked** | `DATABASE_URL` or `BUTTERPOS_DATA_EXPORT` not set |
| A3 | Billing/payment status source | **Blocked** | `BILLING_API_URL` not set — need billing API endpoint |
| A4 | Chatwoot runs locally via Docker | **Verified** | Health OK at localhost:3000; Step 0.1 spike passed (mean 123ms) |
| A5 | MCP server owned by backend teammate | **Manual** | Architectural split confirmed (D-4); `MCP_SERVER_URL` pending Step 0.6 |
| A6 | WhatsApp export for KB audit | **Manual** | Step 0.3 tooling ready; production export not yet provided |
| A7 | widget → middleware → Chatwoot | **Verified** | D-2 locked + Step 0.1 spike validates middleware→Chatwoot API path |

Validation script: `spikes/0.4_assumption_validation/verify_assumptions.py`  
Latest report: `spikes/0.4_assumption_validation/results/validation_report_*.json`

### Consequences

- **A1, A2, A3 blocked** — Phase 1 Tasks 1.6 (mapping) and 1.7 (seeding) cannot proceed without data source credentials.
- **A5** — Step 0.6 blocked until backend teammate provides MCP server URL + tool catalog.
- **A6** — Phase 2 KB gate (D-10) remains open until production WhatsApp export provided.
- Re-run validation after adding env vars: `python spikes/0.4_assumption_validation/verify_assumptions.py`

---

## D-8 — Provider API keys available today

**Status:** Superseded by D-11 (2026-06-01)

### Context

Originally Step 0.2 could only score providers the team had direct API keys for (OpenAI only). The team later adopted OpenRouter as a single gateway.

### Original decision (archived)

| Provider | Available today |
|----------|-----------------|
| OpenAI (e.g. GPT-4o / 4o-mini) | **Yes** |
| Google Gemini | No — test when key available |
| Anthropic Claude | No — test when key available |

See **D-11** for current approach.

---

## D-11 — LLM gateway: OpenRouter

**Status:** Locked (2026-06-01)

### Context

V1 needs access to multiple paid LLM vendors (OpenAI, Anthropic, Gemini) for evaluation and fallback. Managing separate API keys and SDK integrations per vendor conflicts with D-3 (`LLMProvider` isolation). The team chose **OpenRouter** as a unified gateway: one API key, swap models via slug (e.g. `openai/gpt-4o`, `anthropic/claude-3.5-sonnet`, `google/gemini-2.0-flash-001`).

### Decision

- All V1 LLM calls go through **`OpenRouterProvider`** — a single adapter using OpenRouter's OpenAI-compatible HTTP API.
- The core **never** imports vendor LLM SDKs. The spike adapter lives at `spikes/0.2_llm_eval/providers/openrouter_provider.py`; Phase 1 moves it to `app/core/ai/`.
- Model selection is **config-only**: change `LLM_PRIMARY_MODEL`, `LLM_FALLBACK_MODEL`, or CLI `--models` — no code changes.
- HTTP client: `openai` Python package pointed at `https://openrouter.ai/api/v1` (transport only, not a vendor coupling in core).

### Env vars

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | Yes | API key from [openrouter.ai/keys](https://openrouter.ai/keys) |
| `LLM_PRIMARY_MODEL` | Phase 1+ | Default primary slug, e.g. `openai/gpt-4o` |
| `LLM_FALLBACK_MODEL` | Phase 1+ | Default fallback slug, e.g. `openai/gpt-4o-mini` |
| `LLM_JUDGE_MODEL` | Eval | Fixed judge for Roman Urdu scoring |
| `OPENROUTER_APP_URL` | Optional | Attribution header for OpenRouter rankings |
| `OPENROUTER_APP_NAME` | Optional | App name header (default: ButterPOS Support Agent) |

### Consequences

- D-8 (per-vendor keys) is superseded — one `OPENROUTER_API_KEY` covers all vendors OpenRouter supports.
- Step 0.2 eval and Step 0.6 portability tests can compare OpenAI, Anthropic, and Gemini models in one run via `--models`.
- Cost estimates use approximate per-model pricing in the adapter; refine from OpenRouter usage/billing data in production.
- PII masking (Phase 1) remains mandatory — data still routes to third-party LLM vendors via OpenRouter.

---

## D-9 — Primary + fallback LLM model

**Status:** Pending — harness ready; live eval blocked until `OPENROUTER_API_KEY` is set in `.env`

### Context

Step 0.2 evaluates OpenRouter model slugs (default: `openai/gpt-4o`, `openai/gpt-4o-mini`) against a 50-query ButterPOS support dataset through the `LLMProvider` interface. Scoring uses D-5 bars: Roman Urdu ≥75% acceptable (fixed judge model), latency p95 <8s, cost per 1K tokens.

Any OpenRouter slug can be compared in one run — no per-vendor API keys needed (D-11).

### Decision

_Pending live eval run._ Expected selection logic (implemented in `spikes/0.2_llm_eval/run_eval.py`):

1. **Primary** — among models passing all D-5 bars, highest Roman Urdu acceptability; tie-break lower latency.
2. **Fallback** — among remaining D-5 passers, lowest cost per 1K tokens.

### Candidates (default eval set)

| Model slug | Vendor | Eval status |
|------------|--------|-------------|
| `openai/gpt-4o` | OpenAI via OpenRouter | Pending |
| `openai/gpt-4o-mini` | OpenAI via OpenRouter | Pending |
| `anthropic/claude-3.5-sonnet` | Anthropic via OpenRouter | Optional — pass via `--models` |
| `google/gemini-2.0-flash-001` | Google via OpenRouter | Optional — pass via `--models` |

### Consequences

- Phase 1 `LLMProvider` factory defaults to D-9 primary slug from `LLM_PRIMARY_MODEL`.
- MCP tool-calling validation (Step 0.6) confirms chosen models support function/tool calls via OpenRouter.
- Swap primary/fallback anytime by changing env vars — no adapter rewrite.

### How to complete

```bash
# Add OPENROUTER_API_KEY to .env (never commit)
cd spikes/0.2_llm_eval && ../../.venv/bin/pip install openai python-dotenv
../../.venv/bin/python run_eval.py
# Compare cross-vendor:
../../.venv/bin/python run_eval.py --models openai/gpt-4o anthropic/claude-3.5-sonnet google/gemini-2.0-flash-001
```

Update this ADR with scorecard numbers from `results/eval_report_*.json`.

---

## D-12 — Ticketing read cache as provider decorator

**Status:** Locked (2026-06-02)

### Context

Task 1.5 requires Redis-backed caching for `get_ticket` and `get_or_create_contact` without breaking provider isolation.

### Decision

Wrap the configured `TicketingProvider` in `CachingTicketingProvider` at factory time. Redis stores serialized `StandardTicket` / `StandardContact` JSON with TTLs 60s / 24h. Webhook processing invalidates affected keys; write paths refresh or invalidate.

### Consequences

- Core never imports Redis directly in ChatwootAdapter.
- Swapping ticketing platform keeps cache logic unchanged.
- Postgres `ticket_cache` remains the durable mirror (polling); Redis is hot read path only.

---

## D-13 — Webhook rate limits ack with HTTP 200

**Status:** Locked (2026-06-02)

### Context

Task 1.5.2 adds per-user and per-restaurant sliding-window limits on inbound Chatwoot `message_created` webhooks. Chatwoot retries non-2xx responses, which would amplify abuse and duplicate processing attempts.

### Decision

When a rate limit is exceeded at webhook ingress, return HTTP **`200`** with `status: rate_limited`, mark the idempotency audit row `failed`, and **do not** enqueue Celery. JWT API routes may still use `429` via `RateLimitExceededError`.

### Consequences

- Same ack pattern as duplicate webhooks — platform does not retry storms.
- Rate-limited events are auditable in `webhook_event_log` but not processed.
- Duplicates still skip rate-limit consumption (check runs only on fresh inserts).

---

## D-10 — KB MVP list gates Phase 2

**Status:** Resolved (2026-06-01) — tooling ready; production audit pending WhatsApp export

### Context

Phase 2 builds the knowledge base (bilingual articles, RAG, playbooks). Without a data-driven MVP list derived from real support history, article authoring risks covering the wrong issues or missing high-frequency Roman Urdu topics.

### Decision

Step 0.3 **hard-gates Phase 2 KB work**. The top-30 MVP article list must come from a WhatsApp support export (3–6 months), processed by `spikes/0.3_kb_audit/run_audit.py`, and signed off by the support team.

Phase 1 is **not blocked** by this gate.

### Deliverables

| Item | Status |
|------|--------|
| Categorizer + MVP generator | Ready — `spikes/0.3_kb_audit/run_audit.py` |
| 30-row CSV template | Ready — `spikes/0.3_kb_audit/templates/mvp_articles_template.csv` |
| Demo frequency report | Sample only — `sample_data/sample_messages.json` (30 msgs) |
| Production frequency report | **Pending** — requires WhatsApp export + author names |

### Consequences

- Phase 2 KB article sprint starts only after production MVP CSV is signed off in `PROGRESS.md`.
- Articles marked `roman_urdu_needed=Y` in the MVP sheet require bilingual content (`content_ur` per Phase 1 schema).
- `existing_doc` column must be filled manually before Phase 2 to avoid duplicating internal docs.

### How to complete

```bash
python spikes/0.3_kb_audit/run_audit.py \
  --input /path/to/whatsapp_export.json \
  --authors "Author1,Author2,Author3"
```

Review output in `spikes/0.3_kb_audit/results/mvp_articles_*.csv` and sign off with support team.
