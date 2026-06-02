"""Chatwoot client auth and HTTP tests — Task 1.3 sub-step 1."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from app.core.config import Settings
from app.providers.ticketing.chatwoot.auth import missing_config_fields, resolve_api_token
from app.providers.ticketing.chatwoot.client import ChatwootClient
from app.providers.ticketing.chatwoot.errors import ChatwootAPIError, ChatwootAuthError, ChatwootConfigError
from app.providers.ticketing.chatwoot_adapter import ChatwootAdapter


def _settings(**overrides: object) -> Settings:
    base = {
        "_env_file": None,
        "chatwoot_base_url": "http://localhost:3000",
        "chatwoot_api_token": "test-token",
        "chatwoot_account_id": 1,
        "chatwoot_inbox_id": 42,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_resolve_api_token_from_settings() -> None:
    assert resolve_api_token(_settings()) == "test-token"


def test_resolve_api_token_missing_raises() -> None:
    with pytest.raises(ChatwootAuthError, match="CHATWOOT_API_TOKEN"):
        resolve_api_token(_settings(chatwoot_api_token=""))


def test_missing_config_fields() -> None:
    assert missing_config_fields(_settings()) == []
    missing = missing_config_fields(_settings(chatwoot_api_token="", chatwoot_account_id=0))
    assert "CHATWOOT_API_TOKEN" in missing
    assert "CHATWOOT_ACCOUNT_ID" in missing


def test_client_sends_api_access_token_header() -> None:
    seen: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["token"] = request.headers["api_access_token"]
        return httpx.Response(200, json={"version": "3.0.0"})

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        client = ChatwootClient(_settings(), transport=transport)
        await client.ping()
        await client.close()

    asyncio.run(_run())
    assert seen["token"] == "test-token"


def test_client_ping_returns_latency() -> None:
    async def _run() -> None:
        transport = httpx.MockTransport(lambda _request: httpx.Response(200, json={}))
        client = ChatwootClient(_settings(), transport=transport)
        latency_ms = await client.ping()
        await client.close()
        assert latency_ms >= 0.0

    asyncio.run(_run())


def test_client_maps_401_to_auth_error() -> None:
    async def _run() -> None:
        transport = httpx.MockTransport(lambda _request: httpx.Response(401))
        client = ChatwootClient(_settings(), transport=transport)
        with pytest.raises(ChatwootAuthError, match="401"):
            await client.request("GET", "/api")
        await client.close()

    asyncio.run(_run())


def test_client_maps_404_to_api_error() -> None:
    async def _run() -> None:
        transport = httpx.MockTransport(lambda _request: httpx.Response(404))
        client = ChatwootClient(_settings(), transport=transport)
        with pytest.raises(ChatwootAPIError, match="404"):
            await client.request("GET", "/api/v1/accounts/1/conversations/999")
        await client.close()

    asyncio.run(_run())


def test_client_retries_on_503() -> None:
    attempts = {"count": 0}

    async def handler(_request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] < 2:
            return httpx.Response(503)
        return httpx.Response(200, json={})

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        client = ChatwootClient(_settings(chatwoot_max_retries=3), transport=transport)
        response = await client.request("GET", "/api")
        await client.close()
        assert response.status_code == 200
        assert attempts["count"] == 2

    asyncio.run(_run())


def test_adapter_health_check_success() -> None:
    async def _run() -> None:
        transport = httpx.MockTransport(lambda _request: httpx.Response(200, json={}))
        adapter = ChatwootAdapter(_settings(), client=ChatwootClient(_settings(), transport=transport))
        health = await adapter.health_check()
        assert health.healthy is True
        assert health.latency_ms is not None
        assert health.provider == "chatwoot"

    asyncio.run(_run())


def test_adapter_health_check_missing_config() -> None:
    async def _run() -> None:
        adapter = ChatwootAdapter(_settings(chatwoot_api_token=""))
        health = await adapter.health_check()
        assert health.healthy is False
        assert "CHATWOOT_API_TOKEN" in (health.message or "")

    asyncio.run(_run())


def test_adapter_health_check_auth_failure() -> None:
    async def _run() -> None:
        transport = httpx.MockTransport(lambda _request: httpx.Response(401))
        adapter = ChatwootAdapter(_settings(), client=ChatwootClient(_settings(), transport=transport))
        health = await adapter.health_check()
        assert health.healthy is False
        assert "401" in (health.message or "")

    asyncio.run(_run())


def test_client_ensure_configured_raises() -> None:
    client = ChatwootClient(_settings(chatwoot_base_url=""))
    with pytest.raises(ChatwootConfigError, match="CHATWOOT_BASE_URL"):
        client.ensure_configured()
