from mcp.server.fastmcp import FastMCP

# Create MCP server
mcp = FastMCP("ButterPOS")

# ── DIAGNOSTIC TOOLS (read-only, safe) ──

@mcp.tool()
def check_printer_status() -> dict:
    """Check if the POS printer is connected and working."""
    # In real app: actual printer check via Android API
    # For testing: return simulated data
    return {
        "printer_connected": False,
        "printer_ip": "192.168.1.50",
        "expected_ip": "192.168.1.100",
        "spooler_running": True,
        "last_print": "2026-03-18 14:30:00",
        "error": "IP address mismatch"
    }

@mcp.tool()
def get_ip_config() -> dict:
    """Get the current network IP configuration of the POS device."""
    return {
        "current_ip": "192.168.1.50",
        "expected_ip": "192.168.1.100",
        "gateway": "192.168.1.1",
        "dns": "8.8.8.8",
        "network_type": "WiFi",
        "signal_strength": "Good"
    }

@mcp.tool()
def get_system_info() -> dict:
    """Get POS device system information."""
    return {
        "device": "Samsung Galaxy Tab A8",
        "os": "Android 13",
        "app_version": "3.2.1",
        "ram_available": "2.1 GB",
        "storage_free": "12.4 GB",
        "uptime": "4 days 6 hours",
        "battery": "78%"
    }

@mcp.tool()
def check_network() -> dict:
    """Check network connectivity of the POS device."""
    return {
        "internet": True,
        "gateway_ping": "2ms",
        "dns_resolution": True,
        "pos_server_reachable": True,
        "latency_to_server": "45ms"
    }

@mcp.tool()
def get_error_logs(last_n: int = 10) -> dict:
    """Get recent error logs from the POS application."""
    return {
        "logs": [
            {"time": "14:30:05", "level": "ERROR", "msg": "Printer connection failed: 192.168.1.50 not responding"},
            {"time": "14:30:03", "level": "WARN", "msg": "IP address changed from 192.168.1.100 to 192.168.1.50"},
            {"time": "14:29:58", "level": "ERROR", "msg": "Print job #4521 failed: printer offline"},
            {"time": "14:25:00", "level": "INFO", "msg": "Network reconnected"},
            {"time": "14:24:55", "level": "WARN", "msg": "WiFi signal weak"},
        ]
    }

# ── FIX TOOLS (write actions) ──

@mcp.tool()
def set_printer_ip(ip_address: str) -> dict:
    """Change the printer IP address in POS configuration."""
    # In real app: actually changes config
    return {
        "success": True,
        "previous_ip": "192.168.1.50",
        "new_ip": ip_address,
        "message": f"Printer IP updated to {ip_address}"
    }

@mcp.tool()
def restart_print_service() -> dict:
    """Restart the print spooler service."""
    return {
        "success": True,
        "message": "Print service restarted successfully",
        "printer_status": "online"
    }

@mcp.tool()
def restart_pos_app() -> dict:
    """Restart the ButterPOS application."""
    return {
        "success": True,
        "message": "POS application restarted",
        "app_status": "running",
        "startup_time": "3.2 seconds"
    }

@mcp.tool()
def clear_app_cache() -> dict:
    """Clear the POS application cache."""
    return {
        "success": True,
        "cache_cleared": "48 MB",
        "message": "Cache cleared successfully"
    }

# ── MENU TOOLS ──

@mcp.tool()
def add_menu_item(name: str, price: float, category: str) -> dict:
    """Add a new item to the POS menu."""
    return {
        "success": True,
        "item_id": "ITEM-0042",
        "name": name,
        "price": price,
        "category": category,
        "message": f"'{name}' added at Rs {price} in {category}"
    }

@mcp.tool()
def update_price(item_name: str, new_price: float) -> dict:
    """Update the price of an existing menu item."""
    return {
        "success": True,
        "item": item_name,
        "old_price": 350,
        "new_price": new_price,
        "message": f"Price of '{item_name}' updated to Rs {new_price}"
    }

@mcp.tool()
def get_menu_items(category: str = None) -> dict:
    """Get all menu items, optionally filtered by category."""
    items = [
        {"name": "Chicken Biryani", "price": 450, "category": "Rice", "in_stock": True},
        {"name": "Beef Burger", "price": 350, "category": "Burgers", "in_stock": True},
        {"name": "Margherita Pizza", "price": 800, "category": "Pizza", "in_stock": False},
        {"name": "Chai", "price": 80, "category": "Drinks", "in_stock": True},
    ]
    if category:
        items = [i for i in items if i["category"].lower() == category.lower()]
    return {"items": items, "total": len(items)}

@mcp.tool()
def mark_out_of_stock(item_name: str) -> dict:
    """Mark a menu item as out of stock."""
    return {
        "success": True,
        "item": item_name,
        "status": "out_of_stock",
        "message": f"'{item_name}' marked as out of stock"
    }

# ── REPORTING TOOLS ──

@mcp.tool()
def get_daily_sales() -> dict:
    """Get today's sales summary."""
    return {
        "date": "2026-03-18",
        "total_orders": 47,
        "total_revenue": 28500,
        "top_items": [
            {"name": "Chicken Biryani", "qty": 15, "revenue": 6750},
            {"name": "Beef Burger", "qty": 12, "revenue": 4200},
            {"name": "Chai", "qty": 35, "revenue": 2800},
        ],
        "payment_methods": {"cash": 12500, "card": 14000, "online": 2000}
    }

# Run the server
if __name__ == "__main__":
    mcp.run()