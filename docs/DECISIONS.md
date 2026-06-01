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
| D-8 | Provider API keys available today | Resolved (2026-06-01) |
| D-9 | Primary + fallback LLM model | Pending (Step 0.2 — live eval blocked on `OPENAI_API_KEY`) |

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

All assumptions **A1–A7 signed off** as stated. Full validation evidence deferred to Step 0.4.

| ID | Assumption | Status |
|----|------------|--------|
| A1 | ButterPOS Android/tablet app codebase access for embedded chat widget | Signed off |
| A2 | Restaurant → Branch → User data accessible (DB read or validated export) | Signed off |
| A3 | Billing/payment status source identifiable (`plan_type`, `payment_due`, `expiry`) | Signed off |
| A4 | Chatwoot runs locally via Docker for dev/staging | Signed off |
| A5 | MCP server owned by backend teammate; this repo is MCP client only | Signed off |
| A6 | WhatsApp support history export available for KB audit (Step 0.3) | Signed off |
| A7 | Chat path is widget → middleware → Chatwoot (not direct) | Signed off |

### Consequences

- Step 0.4 will produce definitive Yes/No evidence for each assumption (scripts, credential checks, repo access verification).
- Blocked assumptions discovered during Step 0.4 will be logged here as amendments.

---

## D-8 — Provider API keys available today

**Status:** Resolved (2026-06-01)

### Context

Step 0.2 (LLM Evaluation) can only score providers the team can authenticate against today. Other candidates are noted for future testing.

### Decision

| Provider | Available today |
|----------|-----------------|
| OpenAI (e.g. GPT-4o / 4o-mini) | **Yes** |
| Google Gemini | No — test when key available |
| Anthropic Claude | No — test when key available |

### Consequences

- Step 0.2 runs full evaluation against OpenAI only initially.
- Gemini and Anthropic are documented as "test when key available"; primary/fallback selection may be updated when additional keys are obtained.
- Fallback selection in Step 0.2 may be limited to OpenAI model variants until a second provider key is available.

---

## D-9 — Primary + fallback LLM model

**Status:** Pending — harness ready; live eval blocked until `OPENAI_API_KEY` is set in `.env`

### Context

Step 0.2 evaluates OpenAI models (`gpt-4o`, `gpt-4o-mini`) against a 50-query ButterPOS support dataset through the `LLMProvider` interface. Scoring uses D-5 bars: Roman Urdu ≥75% acceptable (fixed judge model), latency p95 <8s, cost per 1K tokens.

Gemini and Anthropic deferred per D-8.

### Decision

_Pending live eval run._ Expected selection logic (implemented in `spikes/0.2_llm_eval/run_eval.py`):

1. **Primary** — among models passing all D-5 bars, highest Roman Urdu acceptability; tie-break lower latency.
2. **Fallback** — among remaining D-5 passers, lowest cost per 1K tokens.

### Candidates

| Model | Provider | Eval status |
|-------|----------|-------------|
| `gpt-4o` | OpenAI | Pending |
| `gpt-4o-mini` | OpenAI | Pending |
| Gemini | Google | Deferred (D-8) |
| Claude | Anthropic | Deferred (D-8) |

### Consequences

- Phase 1 `LLMProvider` factory will default to D-9 primary model.
- MCP tool-calling validation (Step 0.6) must confirm chosen models support function/tool calls.
- Re-run eval when Gemini/Anthropic keys arrive to validate cross-provider fallback.

### How to complete

```bash
# Add OPENAI_API_KEY to .env (never commit)
cd spikes/0.2_llm_eval && ../../.venv/bin/pip install openai
../../.venv/bin/python run_eval.py
```

Update this ADR with scorecard numbers from `results/eval_report_*.json`.
