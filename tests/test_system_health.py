"""System health endpoint tests — Task 1.8.1."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.db.session import clear_session_cache, init_engine, shutdown_engine
from app.main import create_app
from app.schemas.system import ComponentHealth, SystemHealthResponse


@pytest.fixture
def health_settings() -> Settings:
    get_settings.cache_clear()
    clear_session_cache()
    return get_settings()


@pytest.fixture
def health_client(health_settings: Settings) -> TestClient:
    init_engine(health_settings)
    client = TestClient(create_app(health_settings))
    yield client
    asyncio.run(shutdown_engine())
    clear_session_cache()
    get_settings.cache_clear()


def test_system_health_ok(health_client: TestClient) -> None:
    healthy = SystemHealthResponse(
        healthy=True,
        app="ButterPOS Support Agent",
        version="0.1.0",
        components=[
            ComponentHealth(name="postgres", healthy=True),
            ComponentHealth(name="redis", healthy=True),
        ],
    )

    with patch(
        "app.api.v1.system.collect_system_health",
        new=AsyncMock(return_value=healthy),
    ):
        response = health_client.get("/api/v1/system/health")

    assert response.status_code == 200
    body = response.json()
    assert body["healthy"] is True
    assert body["app"] == "ButterPOS Support Agent"


def test_system_health_live_probe(health_client: TestClient) -> None:
    """Integration probe when Postgres + Redis are reachable."""
    response = health_client.get("/api/v1/system/health")
    if response.status_code == 503:
        pytest.skip("Postgres or Redis unavailable in this environment")
    assert response.status_code == 200
    body = response.json()
    assert body["healthy"] is True
    names = {c["name"] for c in body["components"]}
    assert names == {"postgres", "redis"}


def test_system_health_degraded_returns_503(health_client: TestClient) -> None:
    degraded = SystemHealthResponse(
        healthy=False,
        app="ButterPOS Support Agent",
        version="0.1.0",
        components=[
            ComponentHealth(name="postgres", healthy=False, message="down"),
            ComponentHealth(name="redis", healthy=True),
        ],
    )

    with patch(
        "app.api.v1.system.collect_system_health",
        new=AsyncMock(return_value=degraded),
    ):
        response = health_client.get("/api/v1/system/health")

    assert response.status_code == 503
    assert response.json()["healthy"] is False
