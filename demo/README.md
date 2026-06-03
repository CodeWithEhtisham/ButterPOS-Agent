# ButterPOS demo POS data (MCP)

The remote MCP server (`MCP_SERVER_URL`, typically `http://127.0.0.1:3001/mcp`) persists menu/printer state to:

`demo/pos_mcp/demo_store.json`

If that file is missing, write tools such as `create_menu_item` fail with:

`No such file or directory: .../demo/pos_mcp/demo_store.json`

## Fix

Ensure the file exists (seed is committed in this repo):

```bash
ls -la demo/pos_mcp/demo_store.json
```

Restart the MCP server if it cached a startup error, then retry the chat tool call.

## Local stdio MCP (optional)

`demo/chat/` can run a local MCP server via `demo/pos_mcp/server.py` when that script is present. Production middleware uses the **remote** URL in `.env`, not stdio.
