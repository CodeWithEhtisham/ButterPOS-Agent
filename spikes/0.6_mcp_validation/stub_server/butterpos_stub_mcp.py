#!/usr/bin/env python3
"""
ButterPOS STUB MCP Server — Step 0.6 placeholder until backend teammate ships production server.

Exposes the four tools the execution plan expects for validation:
  - get_system_info   (Tier 1 — read)
  - check_printer     (Tier 1 — read)
  - get_sales         (Tier 1 — read)
  - add_menu_item     (Tier 2 — fix)

Run via stdio (default MCP transport):
  python butterpos_stub_mcp.py

Replace this stub by pointing MCP client at the production server when ready.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "ButterPOS-Stub",
    instructions=(
        "Stub ButterPOS diagnostic MCP server for Phase 0 validation. "
        "Returns synthetic data — not connected to real POS devices."
    ),
)

# In-memory stub state
_MENU: list[dict[str, str | float]] = [
    {"id": "item-1", "name": "Chicken Biryani", "price": 450.0},
    {"id": "item-2", "name": "Karahi", "price": 1200.0},
]


@mcp.tool()
def get_system_info(device_id: str = "tablet-001") -> dict[str, str | bool]:
    """Return ButterPOS tablet system information for diagnostics."""
    return {
        "device_id": device_id,
        "app_version": "3.2.1",
        "os": "Android 12",
        "sync_status": "pending",
        "last_sync_at": "2026-06-01T08:00:00Z",
        "online": True,
    }


@mcp.tool()
def check_printer(branch_id: str) -> dict[str, str | bool]:
    """Check receipt/KOT printer status for a branch."""
    return {
        "branch_id": branch_id,
        "printer_name": "EPSON-TM-T88VI",
        "status": "offline",
        "connection": "bluetooth",
        "last_print_at": "2026-06-01T07:45:00Z",
        "suggested_action": "restart_printer",
    }


@mcp.tool()
def get_sales(branch_id: str, date: str = "2026-06-01") -> dict[str, str | float | int]:
    """Get sales summary for a branch on a given date (read-only)."""
    return {
        "branch_id": branch_id,
        "date": date,
        "order_count": 47,
        "gross_total": 125400.0,
        "currency": "PKR",
    }


@mcp.tool()
def add_menu_item(
    branch_id: str,
    name: str,
    price: float,
    category: str = "Main",
) -> dict[str, str | float | bool]:
    """Add a menu item to a branch menu (Tier 2 — requires agent authorization in production)."""
    item_id = f"item-{len(_MENU) + 1}"
    entry = {
        "id": item_id,
        "branch_id": branch_id,
        "name": name,
        "price": price,
        "category": category,
    }
    _MENU.append(entry)
    return {
        "success": True,
        "item_id": item_id,
        "branch_id": branch_id,
        "name": name,
        "price": price,
        "category": category,
        "message": f"Added '{name}' to branch {branch_id}",
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
