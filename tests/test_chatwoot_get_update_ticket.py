"""ChatwootAdapter get_ticket / update_status tests — Task 1.3 sub-step 3."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from app.core.config import Settings
from app.models.standard import StandardStatus, UpdateStatusRequest
from app.providers.ticketing.chatwoot.client import ChatwootClient
from app.providers.ticketing.chatwoot.errors import ChatwootAPIError
from app.providers.ticketing.chatwoot.mappers import (
    STANDARD_STATUS_ATTRIBUTE,
    chatwoot_status_to_standard,
    standard_status_to_chatwoot,
    conversation_to_standard_ticket,
)
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


def _conversation(
    *,
    conversation_id: int = 9001,
    status: str = "open",
    custom_attributes: dict | None = None,
) -> dict:
    return {
        "id": conversation_id,
        "status": status,
        "contact": {"id": 101},
        "labels": ["billing"],
        "custom_attributes": custom_attributes or {"subject": "Sync issue"},
        "created_at": 1_700_000_000,
    }


@pytest.mark.parametrize(
    ("standard", "chatwoot"),
    [
        (StandardStatus.OPEN, "open"),
        (StandardStatus.RESOLVED, "resolved"),
        (StandardStatus.PENDING, "pending"),
        (StandardStatus.SNOOZED, "snoozed"),
        (StandardStatus.IN_PROGRESS, "open"),
        (StandardStatus.CLOSED, "resolved"),
        (StandardStatus.REOPENED, "open"),
    ],
)
def test_standard_to_chatwoot_mapping(standard: StandardStatus, chatwoot: str) -> None:
    assert standard_status_to_chatwoot(standard) == chatwoot


def test_chatwoot_to_standard_uses_custom_attribute() -> None:
    status = chatwoot_status_to_standard(
        "open",
        {"standard_status": "in_progress"},
    )
    assert status is StandardStatus.IN_PROGRESS


def test_conversation_to_standard_ticket_reads_custom_status() -> None:
    ticket = conversation_to_standard_ticket(
        _conversation(status="open", custom_attributes={"standard_status": "escalated"}),
    )
    assert ticket.status is StandardStatus.ESCALATED


def test_get_ticket_fetches_conversation() -> None:
    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET" and request.url.path.endswith("/conversations/9001"):
                return httpx.Response(200, json=_conversation())
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        adapter = ChatwootAdapter(_settings(), client=ChatwootClient(_settings(), transport=transport))
        ticket = await adapter.get_ticket("9001")
        await adapter._client.close()
        assert ticket.provider_ticket_id == "9001"
        assert ticket.subject == "Sync issue"
        assert ticket.tags == ["billing"]

    asyncio.run(_run())


def test_update_status_toggles_and_persists_standard_status() -> None:
    calls: list[tuple[str, str, dict | None]] = []
    stored_attrs: dict = {"subject": "Sync issue"}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        calls.append((request.method, request.url.path, body))
        if request.url.path.endswith("/toggle_status"):
            stored_attrs[STANDARD_STATUS_ATTRIBUTE] = body["status"] if body else None
            return httpx.Response(200, json={"payload": {"success": True, "current_status": "open"}})
        if request.url.path.endswith("/custom_attributes"):
            stored_attrs.update(body.get("custom_attributes", {}) if body else {})
            return httpx.Response(200, json={"custom_attributes": stored_attrs})
        if request.method == "GET" and request.url.path.endswith("/conversations/9001"):
            return httpx.Response(
                200,
                json=_conversation(
                    status="open",
                    custom_attributes=dict(stored_attrs),
                ),
            )
        return httpx.Response(404)

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        adapter = ChatwootAdapter(_settings(), client=ChatwootClient(_settings(), transport=transport))
        ticket = await adapter.update_status(
            UpdateStatusRequest(
                provider_ticket_id="9001",
                status=StandardStatus.IN_PROGRESS,
            ),
        )
        await adapter._client.close()
        assert ticket.status is StandardStatus.IN_PROGRESS
        assert any(path.endswith("/toggle_status") for _, path, _ in calls)
        assert any(path.endswith("/custom_attributes") for _, path, _ in calls)
        toggle_body = next(body for method, path, body in calls if path.endswith("/toggle_status"))
        assert toggle_body == {"status": "open"}

    asyncio.run(_run())


def test_get_ticket_invalid_id() -> None:
    async def _run() -> None:
        adapter = ChatwootAdapter(_settings())
        with pytest.raises(ChatwootAPIError, match="Invalid provider_ticket_id"):
            await adapter.get_ticket("not-numeric")

    asyncio.run(_run())
