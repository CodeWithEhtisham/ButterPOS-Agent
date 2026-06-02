"""Webhook receiver endpoint tests — Task 1.4 sub-step 1."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.api.deps import ticketing_provider_dep
from app.core.config import Settings, get_settings
from app.main import create_app
from app.models.standard import StandardEvent, StandardEventType
from app.providers.ticketing.chatwoot.webhooks import compute_chatwoot_signature
from app.providers.ticketing.factory import get_ticketing_provider
from fastapi.testclient import TestClient

WEBHOOK_SECRET = "whsec-test-receiver"


@pytest.fixture
def webhook_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    get_settings.cache_clear()
    get_ticketing_provider.cache_clear()
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-at-least-32-characters-long")
    monkeypatch.setenv("API_CLIENT_ID", "test-widget")
    monkeypatch.setenv("API_CLIENT_SECRET", "test-client-secret-value")
    monkeypatch.setenv("CHATWOOT_BASE_URL", "http://localhost:3000")
    monkeypatch.setenv("CHATWOOT_API_TOKEN", "test-token")
    monkeypatch.setenv("CHATWOOT_ACCOUNT_ID", "1")
    monkeypatch.setenv("CHATWOOT_INBOX_ID", "42")
    monkeypatch.setenv("CHATWOOT_WEBHOOK_SECRET", WEBHOOK_SECRET)
    return get_settings()


def _signed_request(body: bytes, secret: str = WEBHOOK_SECRET) -> dict[str, str]:
    ts = str(int(time.time()))
    return {
        "X-Chatwoot-Signature": compute_chatwoot_signature(secret, ts, body),
        "X-Chatwoot-Timestamp": ts,
        "Content-Type": "application/json",
    }


def test_chatwoot_webhook_accepts_valid_signed_payload(webhook_settings: Settings) -> None:
    payload = {
        "event": "message_created",
        "id": 12345,
        "content": "Printer offline hai",
        "message_type": "incoming",
        "created_at": "2026-03-04T10:30:00Z",
        "sender": {"id": 101, "type": "contact"},
        "conversation": {"id": 5678},
    }
    body = json.dumps(payload).encode()
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/webhooks/chatwoot",
        content=body,
        headers=_signed_request(body),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert data["event_type"] == "message_created"
    assert data["provider_event_id"] == "12345"
    assert data["provider_ticket_id"] == "5678"
    assert data["idempotency_key"] == "message_created:12345"


def test_chatwoot_webhook_rejects_invalid_signature(webhook_settings: Settings) -> None:
    body = b'{"event":"message_created","id":1,"conversation":{"id":2}}'
    headers = _signed_request(body, secret="wrong-secret")
    client = TestClient(create_app())
    response = client.post("/api/v1/webhooks/chatwoot", content=body, headers=headers)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid webhook signature"


def test_chatwoot_webhook_does_not_require_jwt(webhook_settings: Settings) -> None:
    """Chatwoot calls this endpoint directly — auth is HMAC-only."""
    body = b'{"event":"message_created","id":99,"created_at":"2026-03-04T10:30:00Z","conversation":{"id":5678}}'
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/webhooks/chatwoot",
        content=body,
        headers=_signed_request(body),
    )
    assert response.status_code == 200


def test_chatwoot_webhook_rejects_invalid_json(webhook_settings: Settings) -> None:
    body = b"not-json"
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/webhooks/chatwoot",
        content=body,
        headers=_signed_request(body),
    )
    assert response.status_code == 400


def test_webhook_service_delegates_to_provider() -> None:
    event = StandardEvent(
        event_type=StandardEventType.MESSAGE_CREATED,
        provider_event_id="1",
        provider_ticket_id="2",
        occurred_at=datetime.now(tz=UTC),
        idempotency_key="message_created:1",
    )
    provider = MagicMock()
    provider.provider_name = "chatwoot"
    provider.verify_webhook = AsyncMock(return_value=True)
    provider.parse_webhook = AsyncMock(return_value=event)

    app = create_app()
    app.dependency_overrides[ticketing_provider_dep] = lambda: provider
    body = b'{"event":"message_created","id":1,"created_at":"2026-03-04T10:30:00Z","conversation":{"id":2}}'

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/webhooks/chatwoot",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200
        provider.verify_webhook.assert_awaited_once()
        provider.parse_webhook.assert_awaited_once()
    finally:
        app.dependency_overrides.clear()
