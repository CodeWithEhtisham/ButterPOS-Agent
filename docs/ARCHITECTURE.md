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

---

## Caching strategy

<!-- Task 1.5: Ticket cache (60s TTL), contact cache (24h), webhook-driven invalidation. -->

---

## Agent loop

<!-- Phase 2: Playbook selection, tiered authorization, tool routing, escalation. -->
