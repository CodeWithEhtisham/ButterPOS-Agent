#!/usr/bin/env python3
"""
Demo Restaurant POS MCP server (FastMCP).

Exposes menu, tax, printer, system, and sales tools for local middleware testing.
State is persisted to demo/pos_mcp/demo_store.json.

Run (HTTP — matches MCP_SERVER_URL=http://127.0.0.1:3001/mcp):
  python demo/pos_mcp/server.py
  python demo/pos_mcp/server.py --transport=streamable-http --port=3001

Run (stdio — MCP Inspector / spikes only):
  python demo/pos_mcp/server.py --transport=stdio
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mcp.server.fastmcp import FastMCP

from demo.pos_mcp.state import STORE, MenuItem

mcp = FastMCP(
    "ButterPOS-Demo-POS",
    instructions=(
        "Demo ButterPOS restaurant MCP server. For printer problems, prefer "
        "troubleshoot_printer — it runs the full agent runbook (check status → "
        "IP/pairing → restart → verify) in one call."
    ),
)


def _item_dict(item: MenuItem) -> dict[str, object]:
    pricing = STORE.item_price_with_tax(item)
    return {
        "id": item.id,
        "branch_id": item.branch_id,
        "name": item.name,
        "price": item.price,
        "category": item.category,
        "tax_rate_percent": pricing["tax_rate_percent"],
        "price_with_tax": pricing["price_with_tax"],
        "currency": STORE.currency,
    }


@mcp.tool()
def list_menu_items(branch_id: str = "demo-branch-karachi") -> dict[str, object]:
    """List all menu items for a branch with tax-inclusive prices."""
    items = [_item_dict(i) for i in STORE.list_items(branch_id)]
    return {"branch_id": branch_id, "count": len(items), "items": items}


@mcp.tool()
def search_menu_items(branch_id: str, query: str) -> dict[str, object]:
    """Search menu items by name or category."""
    items = [_item_dict(i) for i in STORE.search_items(branch_id, query)]
    return {"branch_id": branch_id, "query": query, "count": len(items), "items": items}


@mcp.tool()
def get_menu_item(item_id: str) -> dict[str, object]:
    """Get one menu item by id including tax breakdown."""
    item = STORE.get_item(item_id)
    if item is None:
        return {"found": False, "item_id": item_id, "message": "Item not found"}
    return {"found": True, "item": _item_dict(item)}


@mcp.tool()
def create_menu_item(
    branch_id: str,
    name: str,
    price: float,
    category: str = "Main",
) -> dict[str, object]:
    """Create a new menu item on the branch menu."""
    item = STORE.create_item(branch_id, name, price, category)
    return {
        "success": True,
        "message": f"Created menu item '{item.name}'",
        "item": _item_dict(item),
    }


@mcp.tool()
def update_menu_item(
    item_id: str,
    name: str | None = None,
    price: float | None = None,
    category: str | None = None,
) -> dict[str, object]:
    """Update menu item name, price, and/or category."""
    item = STORE.update_item(item_id, name=name, price=price, category=category)
    if item is None:
        return {"success": False, "item_id": item_id, "message": "Item not found"}
    return {
        "success": True,
        "message": f"Updated item '{item.name}'",
        "item": _item_dict(item),
    }


@mcp.tool()
def set_item_tax(item_id: str, tax_rate_percent: float) -> dict[str, object]:
    """Set tax rate (percent) for a specific menu item."""
    item = STORE.set_item_tax(item_id, tax_rate_percent)
    if item is None:
        return {"success": False, "item_id": item_id, "message": "Item not found"}
    return {
        "success": True,
        "message": f"Tax set to {tax_rate_percent}% for '{item.name}'",
        "item": _item_dict(item),
    }


@mcp.tool()
def get_branch_tax(branch_id: str) -> dict[str, object]:
    """Get default sales tax rate for a branch."""
    rate = STORE.get_branch_tax(branch_id)
    return {"branch_id": branch_id, "tax_rate_percent": rate}


@mcp.tool()
def set_branch_tax(branch_id: str, tax_rate_percent: float) -> dict[str, object]:
    """Set default sales tax rate for a branch (does not override per-item tax)."""
    rate = STORE.set_branch_tax(branch_id, tax_rate_percent)
    return {
        "success": True,
        "branch_id": branch_id,
        "tax_rate_percent": rate,
        "message": f"Branch default tax set to {rate}%",
    }


@mcp.tool()
def troubleshoot_printer(branch_id: str = "demo-branch-karachi") -> dict[str, object]:
    """
    Run the full printer support agent workflow in order:

    1. check_printer — initial status and errors
    2. check_printer_ip or Bluetooth pairing — network path
    3. restart_printer — apply fix when needed
    4. verify_printer_status — confirm printer is online

    Use this when the user says the printer is not working, offline, or not printing.
    """
    return STORE.troubleshoot_printer(branch_id)


@mcp.tool()
def check_printer(branch_id: str) -> dict[str, object]:
    """Step 1 only: check receipt/KOT printer status (prefer troubleshoot_printer for full fix)."""
    printer = STORE.check_printer(branch_id)
    suggested = "none"
    if printer.status != "online":
        suggested = "restart" if printer.connection == "bluetooth" else "reconnect"
    return {
        "branch_id": branch_id,
        "printer_name": printer.printer_name,
        "status": printer.status,
        "connection": printer.connection,
        "ip_address": printer.ip_address,
        "last_print_at": printer.last_print_at,
        "last_error": printer.last_error,
        "queue_depth": printer.queue_depth,
        "pairing_strength": printer.pairing_strength,
        "suggested_action": suggested,
        "hint": "For a full automated fix, call troubleshoot_printer next.",
    }


@mcp.tool()
def get_printer_network(branch_id: str) -> dict[str, object]:
    """Step 2 only: ping printer IP (network) or check Bluetooth pairing strength."""
    result = STORE.get_printer_network(branch_id)
    result["branch_id"] = branch_id
    return result


@mcp.tool()
def restart_printer(branch_id: str) -> dict[str, object]:
    """Step 3 only: restart or reconnect the receipt printer (prefer troubleshoot_printer)."""
    before = STORE.check_printer(branch_id)
    action = "restart" if before.connection.lower() == "bluetooth" else "reconnect"
    after = STORE.fix_printer(branch_id, action)
    return {
        "branch_id": branch_id,
        "action": action,
        "previous_status": before.status,
        "status": after.status,
        "ip_address": after.ip_address,
        "last_error": after.last_error,
        "last_print_at": after.last_print_at,
        "success": after.status == "online",
        "message": (
            f"Printer is {after.status} after '{action}'"
            if after.status == "online"
            else f"Printer still {after.status}: {after.last_error or 'unknown error'}"
        ),
        "hint": "Call check_printer again to verify, or use troubleshoot_printer for all steps.",
    }


@mcp.tool()
def fix_printer(branch_id: str, action: str = "restart") -> dict[str, object]:
    """Single action: restart, reconnect, or clear_queue (use troubleshoot_printer for full runbook)."""
    before = STORE.check_printer(branch_id)
    after = STORE.fix_printer(branch_id, action)
    return {
        "branch_id": branch_id,
        "action": action,
        "previous_status": before.status,
        "status": after.status,
        "last_error": after.last_error,
        "last_print_at": after.last_print_at,
        "success": after.status == "online",
        "message": (
            f"Printer is {after.status} after action '{action}'"
            if after.status == "online"
            else f"Printer still {after.status}: {after.last_error or 'unknown error'}"
        ),
    }


@mcp.tool()
def get_system_info(device_id: str = "tablet-demo-001") -> dict[str, object]:
    """Return ButterPOS tablet system information."""
    return {
        "device_id": device_id,
        "app_version": "3.2.1-demo",
        "os": "Android 12",
        "sync_status": "ok",
        "last_sync_at": STORE._now_iso(),
        "online": True,
        "branch_id": STORE.branch_id,
    }


@mcp.tool()
def get_sales(branch_id: str, date: str = "today") -> dict[str, object]:
    """Get sales summary for a branch (demo synthetic totals)."""
    return {
        "branch_id": branch_id,
        "date": date,
        "order_count": STORE.order_count_today,
        "gross_total": STORE.gross_total_today,
        "currency": STORE.currency,
    }


if __name__ == "__main__":
    port = 3001
    transport = "streamable-http"
    for arg in sys.argv[1:]:
        if arg.startswith("--port="):
            port = int(arg.split("=", 1)[1])
        elif arg.startswith("--transport="):
            transport = arg.split("=", 1)[1]

    if transport in {"streamable-http", "streamable_http"}:
        mcp.settings.port = port
        mcp.settings.host = "127.0.0.1"
        print(f"ButterPOS demo MCP → http://127.0.0.1:{port}/mcp", flush=True)
        mcp.run(transport="streamable-http")
    elif transport == "sse":
        mcp.settings.port = port
        mcp.settings.host = "127.0.0.1"
        print(f"ButterPOS demo MCP (SSE) → http://127.0.0.1:{port}/sse", flush=True)
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")
