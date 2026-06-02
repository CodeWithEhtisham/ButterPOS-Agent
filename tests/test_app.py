"""Tests for FastAPI application factory — Task 1.1 sub-step 1."""

from __future__ import annotations

from app.core.config import get_settings
from app.main import create_app
from fastapi.testclient import TestClient


def test_create_app_metadata() -> None:
    get_settings.cache_clear()
    app = create_app()
    assert app.title == "ButterPOS Support Agent"
    assert app.version == "0.1.0"


def test_app_module_instance() -> None:
    from app.main import app

    client = TestClient(app)
    # OpenAPI docs available at default FastAPI path
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "ButterPOS Support Agent"
