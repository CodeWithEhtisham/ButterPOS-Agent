"""Tests for ticketing provider factory — Task 1.1.6."""

from __future__ import annotations

import asyncio

import pytest
from app.core.config import Settings, get_settings
from app.main import create_app
from app.providers.ticketing.chatwoot_adapter import ChatwootAdapter
from app.providers.ticketing.factory import (
    UnknownTicketingProviderError,
    clear_ticketing_provider_cache,
    create_ticketing_provider,
    get_ticketing_provider,
)
from fastapi.testclient import TestClient

TEST_SECRET = "test-jwt-secret-at-least-32-characters-long"
TEST_CLIENT_ID = "test-widget"
TEST_CLIENT_SECRET = "test-client-secret-value"


@pytest.fixture
def factory_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    get_settings.cache_clear()
    clear_ticketing_provider_cache()
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    monkeypatch.setenv("API_CLIENT_ID", TEST_CLIENT_ID)
    monkeypatch.setenv("API_CLIENT_SECRET", TEST_CLIENT_SECRET)
    monkeypatch.setenv("TICKETING_PROVIDER", "chatwoot")
    monkeypatch.setenv("CHATWOOT_BASE_URL", "http://localhost:3000")
    monkeypatch.setenv("CHATWOOT_API_TOKEN", "test-token")
    monkeypatch.setenv("CHATWOOT_ACCOUNT_ID", "1")
    return get_settings()


def test_factory_returns_chatwoot_adapter(factory_settings: Settings) -> None:
    provider = create_ticketing_provider(factory_settings)
    assert isinstance(provider, ChatwootAdapter)
    assert provider.provider_name == "chatwoot"


def test_factory_unknown_provider_raises(factory_settings: Settings) -> None:
    unknown = factory_settings.model_copy(update={"ticketing_provider": "zoho"})
    with pytest.raises(UnknownTicketingProviderError, match="zoho"):
        create_ticketing_provider(unknown)


def test_get_ticketing_provider_is_cached(factory_settings: Settings) -> None:
    first = get_ticketing_provider()
    second = get_ticketing_provider()
    assert first is second


def test_chatwoot_adapter_health_with_config(factory_settings: Settings) -> None:
    adapter = ChatwootAdapter(factory_settings)
    health = asyncio.run(adapter.health_check())
    assert health.healthy is True
    assert health.provider == "chatwoot"


def test_chatwoot_adapter_health_missing_config() -> None:
    settings = Settings(
        _env_file=None,
        chatwoot_base_url="",
        chatwoot_api_token="",
        chatwoot_account_id=0,
    )
    adapter = ChatwootAdapter(settings)
    health = asyncio.run(adapter.health_check())
    assert health.healthy is False
    assert "CHATWOOT_BASE_URL" in (health.message or "")


def test_ticketing_health_endpoint(factory_settings: Settings) -> None:
    get_settings.cache_clear()
    clear_ticketing_provider_cache()
    client = TestClient(create_app())

    token_response = client.post(
        "/api/v1/auth/token",
        json={
            "client_id": TEST_CLIENT_ID,
            "client_secret": TEST_CLIENT_SECRET,
            "subject": "staff-1",
        },
    )
    token = token_response.json()["access_token"]

    response = client.get(
        "/api/v1/system/ticketing-health",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "chatwoot"
    assert body["healthy"] is True
