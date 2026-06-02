# MCP Integration

Model Context Protocol client contract for the ButterPOS AI Support Agent middleware.

---

## Ownership split

| Component | Owner | Repo |
|-----------|-------|------|
| **MCP server** | Backend teammate | ButterPOS backend (knows models, APIs, business logic) |
| **MCP client** | This middleware | `ButterPOS-Agent` |
| **Contract** | Shared | This document — keep in sync with server team |

**Phase 0 (2026-06-01):** Production MCP server not ready. Validation uses **stub server** at `spikes/0.6_mcp_validation/stub_server/butterpos_stub_mcp.py`. Replace with production server via config when available — no agent loop code changes.

---

## Transport

| Environment | Transport | Config |
|-------------|-----------|--------|
| Phase 0 stub | **stdio** | `python stub_server/butterpos_stub_mcp.py` (subprocess) |
| Production (TBD) | stdio or SSE | `MCP_SERVER_URL` or command from teammate |

Client implementation: `spikes/0.6_mcp_validation/client/mcp_client.py` (Phase 1 → `app/core/mcp/client.py`).

---

## Auth

| Environment | Auth |
|-------------|------|
| Phase 0 stub | None (local subprocess) |
| Production (TBD) | TBD with backend teammate — document token/header here when known |

---

## Tool catalog

Validated against stub (2026-06-01). Production server must expose **at minimum** these tools (names stable for playbook mapping):

| Tool | Tier | Input | Output (stub shape) |
|------|------|-------|------------------------|
| `get_system_info` | 1 — read | `device_id: str` | `{device_id, app_version, os, sync_status, last_sync_at, online}` |
| `check_printer` | 1 — read | `branch_id: str` | `{branch_id, printer_name, status, connection, last_print_at, suggested_action}` |
| `get_sales` | 1 — read | `branch_id: str`, `date: str` | `{branch_id, date, order_count, gross_total, currency}` |
| `add_menu_item` | 2 — fix | `branch_id, name, price, category` | `{success, item_id, branch_id, name, price, category, message}` |

Tier 3 actions (always escalate) are not exposed as MCP tools in V1.

---

## Request/response shapes

### MCP `call_tool` (client → server)

```json
{
  "name": "check_printer",
  "arguments": { "branch_id": "branch-101" }
}
```

### MCP tool result (server → client)

Text content JSON (parsed by client):

```json
{
  "branch_id": "branch-101",
  "printer_name": "EPSON-TM-T88VI",
  "status": "offline",
  "connection": "bluetooth",
  "suggested_action": "restart_printer"
}
```

### Function-calling schema (OpenAI-compatible / OpenRouter)

Middleware converts MCP `inputSchema` → OpenAI-compatible `tools[]` format. Same catalog used for all models via OpenRouter (D-3/D-4/D-11).

---

## LLM provider compatibility

Tool-calling validated via `LLMProvider` interface (Step 0.6):

- **Direct MCP probe:** all 4 stub tools callable without LLM
- **LLM portability:** same MCP tool catalog passed to any OpenRouter model slug; client executes `call_tool` on LLM's `tool_calls` response
- **Models tested:** `openai/gpt-4o-mini`, `anthropic/claude-3-haiku` — PASS (2026-06-02); any slug via `--models`
- **Cross-vendor:** compare `anthropic/claude-*`, `google/gemini-*` in one run — no separate API keys (D-11)

Primary/fallback models: see D-9 in `DECISIONS.md`.

---

## Why MCP beat direct tool calling (D-4 record)

See `DECISIONS.md` D-4 validation appendix. Summary:

1. **Provider portability** — one MCP tool catalog; swap LLM by config, not per-vendor tool plumbing
2. **Ownership boundary** — ButterPOS business logic stays in backend MCP server; middleware never imports POS SDKs
3. **Extensibility** — new tools = server + contract update; agent loop unchanged (Super Agent goal)
4. **Standard protocol** — stdio/SSE transport, `list_tools` / `call_tool` — not custom JSON-RPC per integration

---

## Validation

```bash
cd spikes/0.6_mcp_validation
python run_validation.py
```

Reports: `spikes/0.6_mcp_validation/results/mcp_validation_*.json`
