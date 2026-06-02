"""Structured logging and exception handler tests — Task 1.1.8."""

from __future__ import annotations

import json
import logging

import pytest
from app.core.config import Settings, get_settings
from app.core.error_handlers import register_exception_handlers
from app.core.exceptions import AppError
from app.core.logging_config import JsonLogFormatter
from app.main import create_app
from fastapi import FastAPI
from fastapi.testclient import TestClient

TEST_SECRET = "test-jwt-secret-at-least-32-characters-long"
TEST_CLIENT_ID = "test-widget"
TEST_CLIENT_SECRET = "test-client-secret-value"


@pytest.fixture
def log_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    monkeypatch.setenv("API_CLIENT_ID", TEST_CLIENT_ID)
    monkeypatch.setenv("API_CLIENT_SECRET", TEST_CLIENT_SECRET)
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    return get_settings()


@pytest.fixture
def client(log_settings: Settings) -> TestClient:
    get_settings.cache_clear()
    return TestClient(create_app(log_settings))


def test_json_formatter_includes_context_fields() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-123"
    record.user_id = "staff-9"
    record.ticket_id = "conv-42"
    output = json.loads(JsonLogFormatter().format(record))
    assert output["message"] == "hello"
    assert output["request_id"] == "req-123"
    assert output["user_id"] == "staff-9"
    assert output["ticket_id"] == "conv-42"
    assert "timestamp" in output


def test_request_includes_x_request_id_header(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")


def test_http_exception_returns_json_detail(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"]


def test_request_logging_includes_user_id(client: TestClient) -> None:
    records: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.emit = lambda record: records.append(record)
    request_logger = logging.getLogger("app.request")
    request_logger.addHandler(handler)
    request_logger.setLevel(logging.INFO)
    try:
        token_response = client.post(
            "/api/v1/auth/token",
            json={
                "client_id": TEST_CLIENT_ID,
                "client_secret": TEST_CLIENT_SECRET,
                "subject": "staff-log-1",
            },
        )
        token = token_response.json()["access_token"]
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    finally:
        request_logger.removeHandler(handler)

    completed = [r for r in records if "request_completed" in r.getMessage()]
    assert completed
    assert any("staff-log-1" in r.getMessage() for r in completed)


def test_app_error_handler_returns_status() -> None:
    app = FastAPI()

    @app.get("/boom")
    def boom() -> None:
        raise AppError("Mapping failed", status_code=422)

    register_exception_handlers(app, Settings(_env_file=None, debug=True))

    response = TestClient(app).get("/boom")
    assert response.status_code == 422
    assert response.json()["detail"] == "Mapping failed"


def test_unhandled_exception_hidden_when_not_debug(log_settings: Settings) -> None:
    app = create_app(log_settings.model_copy(update={"debug": False}))

    @app.get("/api/v1/test-crash")
    def crash() -> None:
        raise RuntimeError("secret internals")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/v1/test-crash")
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"


def test_unhandled_exception_shown_when_debug(log_settings: Settings) -> None:
    app = create_app(log_settings.model_copy(update={"debug": True}))

    @app.get("/api/v1/test-crash-debug")
    def crash_debug() -> None:
        raise RuntimeError("visible error")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/v1/test-crash-debug")
    assert response.status_code == 500
    assert "visible error" in response.text
