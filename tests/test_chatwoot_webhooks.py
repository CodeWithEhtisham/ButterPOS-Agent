"""Chatwoot webhook verification, parsing, and registration tests — Task 1.3 sub-step 7."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time

import httpx
import pytest
from app.core.config import Settings
from app.models.standard import StandardEventType
from app.providers.ticketing.chatwoot.client import ChatwootClient
from app.providers.ticketing.chatwoot.errors import ChatwootAPIError
from app.providers.ticketing.chatwoot.webhooks import (
    build_idempotency_key,
    compute_chatwoot_signature,
    parse_chatwoot_webhook,
    verify_chatwoot_webhook,
)
from app.providers.ticketing.chatwoot_adapter import ChatwootAdapter


def _settings(**overrides: object) -> Settings:
    base = {
        "_env_file": None,
        "chatwoot_base_url": "http://localhost:3000",
        "chatwoot_api_token": "test-token",
        "chatwoot_account_id": 1,
        "chatwoot_inbox_id": 42,
        "chatwoot_webhook_secret": "whsec-test",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _signed_headers(secret: str, body: bytes, timestamp: int | None = None) -> dict[str, str]:
    ts = str(timestamp or int(time.time()))
    signature = compute_chatwoot_signature(secret, ts, body)
    return {
        "X-Chatwoot-Signature": signature,
        "X-Chatwoot-Timestamp": ts,
    }


def test_verify_chatwoot_webhook_valid_signature() -> None:
    body = b'{"event":"message_created","id":123}'
    headers = _signed_headers("whsec-test", body)
    assert verify_chatwoot_webhook(body, headers, "whsec-test") is True


def test_verify_chatwoot_webhook_invalid_signature() -> None:
    body = b'{"event":"message_created","id":123}'
    headers = _signed_headers("whsec-test", body)
    assert verify_chatwoot_webhook(body, headers, "wrong-secret") is False


def test_verify_chatwoot_webhook_rejects_old_timestamp() -> None:
    body = b'{"event":"message_created","id":123}'
    old_ts = int(time.time()) - 600
    headers = _signed_headers("whsec-test", body, timestamp=old_ts)
    assert verify_chatwoot_webhook(body, headers, "whsec-test", max_age_seconds=300) is False


def test_compute_signature_matches_hmac_spec() -> None:
    secret = "secret"
    timestamp = "1700000000"
    body = b'{"hello":"world"}'
    signed_payload = f"{timestamp}.".encode() + body
    expected = "sha256=" + hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    assert compute_chatwoot_signature(secret, timestamp, body) == expected


def test_parse_message_created_webhook() -> None:
    payload = {
        "event": "message_created",
        "id": 12345,
        "content": "Printer offline hai",
        "message_type": "incoming",
        "created_at": "2026-03-04T10:30:00Z",
        "sender": {"id": 101, "type": "contact"},
        "conversation": {"id": 5678},
    }
    event = parse_chatwoot_webhook(json.dumps(payload).encode())
    assert event.event_type is StandardEventType.MESSAGE_CREATED
    assert event.provider_ticket_id == "5678"
    assert event.provider_event_id == "12345"
    assert event.message_body == "Printer offline hai"
    assert event.message_direction == "incoming"
    assert event.sender_provider_contact_id == "101"
    assert event.idempotency_key == "message_created:12345"


def test_parse_conversation_status_changed_webhook() -> None:
    payload = {
        "event": "conversation_status_changed",
        "id": 5678,
        "status": "resolved",
        "updated_at": "2026-03-04T11:00:00Z",
    }
    event = parse_chatwoot_webhook(json.dumps(payload).encode())
    assert event.event_type is StandardEventType.CONVERSATION_STATUS_CHANGED
    assert event.provider_ticket_id == "5678"
    assert event.idempotency_key == "conversation_status_changed:5678:2026-03-04T11:00:00Z"


def test_parse_webhook_missing_conversation_raises() -> None:
    with pytest.raises(ChatwootAPIError, match="conversation id"):
        parse_chatwoot_webhook(json.dumps({"event": "unknown"}).encode())


def test_adapter_verify_and_parse() -> None:
    payload = {
        "event": "message_created",
        "id": 99,
        "content": "hello",
        "message_type": "outgoing",
        "created_at": "2026-03-04T10:30:00Z",
        "conversation": {"id": 5678},
    }
    body = json.dumps(payload).encode()

    async def _run() -> None:
        adapter = ChatwootAdapter(_settings())
        headers = _signed_headers("whsec-test", body)
        assert await adapter.verify_webhook(body, headers) is True
        event = await adapter.parse_webhook(body, headers)
        assert event.event_type is StandardEventType.MESSAGE_CREATED

    asyncio.run(_run())


def test_list_account_webhooks() -> None:
    async def _run() -> None:
        transport = httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={
                    "payload": {
                        "webhooks": [{"id": 1, "url": "https://example.com/hook"}],
                    },
                },
            ),
        )
        adapter = ChatwootAdapter(_settings(), client=ChatwootClient(_settings(), transport=transport))
        rows = await adapter.list_webhooks()
        await adapter._client.close()
        assert rows[0]["url"] == "https://example.com/hook"

    asyncio.run(_run())


def test_register_webhook_posts_to_chatwoot() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": 5, "secret": "new-whsec"})

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        adapter = ChatwootAdapter(_settings(), client=ChatwootClient(_settings(), transport=transport))
        result = await adapter.register_webhook("https://middleware.example/api/v1/webhooks/chatwoot")
        await adapter._client.close()
        assert result["secret"] == "new-whsec"
        assert captured["body"]["webhook"]["url"].endswith("/webhooks/chatwoot")
        assert "message_created" in captured["body"]["webhook"]["subscriptions"]

    asyncio.run(_run())


def test_build_idempotency_key_message_event() -> None:
    key = build_idempotency_key({"id": 42, "event": "message_created"}, "message_created")
    assert key == "message_created:42"
