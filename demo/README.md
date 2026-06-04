# ButterPOS demo MCP server

Local POS MCP tools (menu, tax, printer, sales) for testing **middleware on :8000**.

Middleware is only the **client** — start this server separately and set in `.env`:

```env
MCP_SERVER_URL=http://127.0.0.1:3001/mcp
MCP_TRANSPORT=streamable_http
```

## Run

**Terminal 1 — MCP server (leave running):**

```bash
cd /path/to/ButterPOS-Agent
source .venv/bin/activate
python demo/pos_mcp/server.py
```

Default: streamable HTTP on **http://127.0.0.1:3001/mcp**

Optional flags:

```bash
python demo/pos_mcp/server.py --transport=streamable-http --port=3001
python demo/pos_mcp/server.py --transport=stdio   # MCP Inspector only
```

**Terminal 2 — middleware:**

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Verify:**

```bash
curl -s http://127.0.0.1:8000/api/v1/chat/health | jq
```

Expect `"ready": true` and `"mcp_tools": 15` (or more).

**Browser chat UI:** http://127.0.0.1:8000/api/v1/chat/ui

## Data file

Writes menu/printer state to:

`demo/pos_mcp/demo_store.json`

If write tools fail with “file not found”, ensure that path exists (committed in repo) and restart the MCP server.

## MCP tools

| Tool | Type | Notes |
|------|------|--------|
| **`troubleshoot_printer`** | **workflow** | **Use for “printer not working”** — runs full runbook |
| `check_printer` | read | Step 1 only |
| `get_printer_network` | read | Step 2 — IP ping or Bluetooth pairing |
| `restart_printer` | write | Step 3 only |
| `fix_printer` | write | Single action (legacy) |
| `list_menu_items` / `search_menu_items` / `get_menu_item` | read | Menu |
| `create_menu_item` / `update_menu_item` / `set_item_tax` | write | Menu |
| `get_branch_tax` / `set_branch_tax` | read / write | Tax |
| `get_system_info` / `get_sales` | read | Diagnostics |

### Printer agent runbook (`troubleshoot_printer`)

1. **check_printer** — status, connection, last error  
2. **check_printer_ip** or **pairing** — network path for LAN/Wi‑Fi, Bluetooth pairing otherwise  
3. **restart_printer** — restart/reconnect when needed  
4. **verify_printer_status** — confirm online  

## Example prompts (chat UI)

- “What's the price of chicken biryani?”
- “Add Mango Lassi for 280 rupees”
- **“My printer is not working”** → should call `troubleshoot_printer` and walk through all steps

See `docs/DEPLOYMENT.md` § “Test middleware + remote MCP” for full API steps.
