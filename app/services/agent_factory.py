"""Build AgentService for API routes and Celery workers."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.core.mcp.factory import ensure_mcp_client, get_mcp_client
from app.core.pii.factory import get_pii_masker
from app.providers.llm.factory import get_llm_provider
from app.services.agent_service import AgentService


async def build_agent_service(settings: Settings | None = None) -> AgentService:
    """Construct AgentService after ensuring MCP is connected."""
    app_settings = settings or get_settings()
    await ensure_mcp_client(app_settings)
    return AgentService(
        app_settings,
        get_llm_provider(),
        get_mcp_client(),
        get_pii_masker(),
    )
