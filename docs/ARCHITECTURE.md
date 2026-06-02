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

Abstract interface in `app/providers/ticketing/base.py` — **11 async methods**:

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

`ChatwootAdapter` implements this in Task 1.3. Factory in Task 1.1.6.

### Provider factory (Task 1.1.6)

- Env: `TICKETING_PROVIDER` (default `chatwoot`)
- Module: `app/providers/ticketing/factory.py`
- Registry maps provider name → builder; lazy import keeps core decoupled
- FastAPI: `ticketing_provider_dep()` in `app/api/deps.py`
- Adding Zoho: implement `ZohoAdapter`, register in `_REGISTRY` — zero core changes

---

## Caching strategy

- **Ticket/contact cache** — Task 1.5 (60s / 24h TTL).
- **PII token map** — Task 1.1.7: Redis `pii:token:{id}` → original value, **24h TTL**. Used to unmask LLM responses. Invalid/expired tokens remain as placeholders in text.

---

## Agent loop

<!-- Phase 2: Playbook selection, tiered authorization, tool routing, escalation. -->
