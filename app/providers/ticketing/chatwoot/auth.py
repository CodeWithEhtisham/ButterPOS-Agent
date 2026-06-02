"""Chatwoot API token resolution — env in V1; Redis override deferred."""

from __future__ import annotations

from app.core.config import Settings
from app.providers.ticketing.chatwoot.errors import ChatwootAuthError


def resolve_api_token(settings: Settings) -> str:
    """Return the Chatwoot agent API token from environment settings."""
    token = settings.chatwoot_api_token.strip()
    if not token:
        raise ChatwootAuthError("CHATWOOT_API_TOKEN is not configured")
    return token


def missing_config_fields(settings: Settings) -> list[str]:
    """Return env var names required before any Chatwoot API call."""
    missing: list[str] = []
    if not settings.chatwoot_base_url.strip():
        missing.append("CHATWOOT_BASE_URL")
    if not settings.chatwoot_api_token.strip():
        missing.append("CHATWOOT_API_TOKEN")
    if not settings.chatwoot_account_id:
        missing.append("CHATWOOT_ACCOUNT_ID")
    return missing
