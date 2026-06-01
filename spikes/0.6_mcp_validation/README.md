# Step 0.6 — MCP client validation spike

**Goal:** Prove middleware works as an **MCP client**, tools fire through `LLMProvider`, and document the MCP contract.

**Stub server:** `stub_server/butterpos_stub_mcp.py` — placeholder until backend teammate ships production MCP server. Swap client config when ready; no middleware code changes.

## Stub tools

| Tool | Tier | Description |
|------|------|-------------|
| `get_system_info` | 1 (read) | Tablet app version, sync status |
| `check_printer` | 1 (read) | Printer connectivity + suggested fix |
| `get_sales` | 1 (read) | Branch sales summary |
| `add_menu_item` | 2 (fix) | Add menu item (stub mutates in-memory list) |

## Run

```bash
pip install mcp openai python-dotenv
cd spikes/0.6_mcp_validation
python run_validation.py
```

With `OPENROUTER_API_KEY` in repo-root `.env`, also runs LLM agent loop to prove **same MCP tools, different OpenRouter model slugs, zero client rewrite** (D-4/D-11):

```bash
python run_validation.py --models openai/gpt-4o anthropic/claude-3.5-sonnet
```

Without API key: direct MCP probe still runs and must pass.

## Architecture

```
run_validation.py
  └── MCPClient (stdio → stub_server/butterpos_stub_mcp.py)
  └── AgentLoop → LLMProvider (OpenRouter) → tool_calls → MCPClient.call_tool()
```

Production: replace stub stdio path with teammate's server command or SSE URL.

## Output

`results/mcp_validation_*.json` — tool catalog, direct probe results, LLM portability tests.
