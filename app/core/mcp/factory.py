"""MCP client lifecycle."""

from __future__ import annotations

import asyncio
import logging

from app.core.config import Settings, get_settings
from app.core.mcp.client import MCPClient

logger = logging.getLogger(__name__)

_mcp_client: MCPClient | None = None


async def ensure_mcp_client(settings: Settings | None = None) -> MCPClient | None:
    """Return cached MCP client, connecting lazily when needed (e.g. Celery worker)."""
    try:
        return get_mcp_client()
    except RuntimeError:
        return await init_mcp_client(settings)


async def init_mcp_client(settings: Settings | None = None) -> MCPClient | None:
    """Connect to configured remote MCP server and cache tool catalog."""
    global _mcp_client
    app_settings = settings or get_settings()
    url = app_settings.mcp_server_url.strip()
    if not url:
        return None

    client = MCPClient.for_url(url, transport=app_settings.mcp_transport)
    try:
        await client.connect()
    except (Exception, asyncio.CancelledError) as exc:
        # MCP SDK may raise CancelledError when the HTTP connect fails (not Exception).
        logger.warning(
            "MCP server not reachable at %s (%s) — start MCP first; chat tools disabled until connected",
            url,
            type(exc).__name__,
        )
        await client.disconnect()
        return None
    _mcp_client = client
    return client


async def shutdown_mcp_client() -> None:
    """Close the persistent MCP session on app shutdown."""
    global _mcp_client
    if _mcp_client is not None:
        await _mcp_client.disconnect()
        _mcp_client = None


def get_mcp_client() -> MCPClient:
    if _mcp_client is None:
        raise RuntimeError("MCP client not initialized — set MCP_SERVER_URL and restart middleware")
    return _mcp_client


def clear_mcp_client_cache() -> None:
    global _mcp_client
    _mcp_client = None
