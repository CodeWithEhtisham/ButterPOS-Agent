"""ChatwootAdapter.create_ticket tests — Task 1.3 sub-step 2."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from app.core.config import Settings
from app.models.standard import CreateTicketRequest, StandardStatus
from app.providers.ticketing.chatwoot.client import ChatwootClient
from app.providers.ticketing.chatwoot.errors import ChatwootAPIError, ChatwootConfigError
from app.providers.ticketing.chatwoot.mappers import chatwoot_status_to_standard, conversation_to_standard_ticket
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


def _conversation_body(conversation_id: int = 9001, contact_id: int = 101) -> dict:
    return {
        "id": conversation_id,
        "inbox_id": 42,
        "contact_id": contact_id,
        "status": "open",
        "contact": {"id": contact_id},
        "labels": [],
        "created_at": 1_700_000_000,
    }


def test_chatwoot_status_mapping() -> None:
    assert chatwoot_status_to_standard("open") is StandardStatus.OPEN
    assert chatwoot_status_to_standard("resolved") is StandardStatus.RESOLVED


def test_conversation_to_standard_ticket() -> None:
    ticket = conversation_to_standard_ticket(_conversation_body(), subject="Printer issue")
    assert ticket.provider_ticket_id == "9001"
    assert ticket.status is StandardStatus.OPEN
    assert ticket.provider_contact_id == "101"
    assert ticket.subject == "Printer issue"


def test_create_ticket_minimal() -> None:
    requests: list[tuple[str, str, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        requests.append((request.method, request.url.path, body))
        if request.method == "POST" and request.url.path.endswith("/conversations"):
            return httpx.Response(200, json=_conversation_body())
        return httpx.Response(404)

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        adapter = ChatwootAdapter(_settings(), client=ChatwootClient(_settings(), transport=transport))
        ticket = await adapter.create_ticket(
            CreateTicketRequest(provider_contact_id="101"),
        )
        await adapter._client.close()
        assert ticket.provider_ticket_id == "9001"
        assert ticket.status is StandardStatus.OPEN
        assert "source_id" in ticket.metadata
        assert requests[0][2]["contact_id"] == 101
        assert requests[0][2]["inbox_id"] == 42
        assert "source_id" in requests[0][2]

    asyncio.run(_run())


def test_create_ticket_with_message_and_tags() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("/conversations") and request.method == "POST":
            return httpx.Response(200, json=_conversation_body())
        if "/messages" in request.url.path:
            return httpx.Response(200, json={"id": 1})
        if request.url.path.endswith("/labels"):
            return httpx.Response(200, json={"payload": ["printer"]})
        return httpx.Response(404)

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        adapter = ChatwootAdapter(_settings(), client=ChatwootClient(_settings(), transport=transport))
        ticket = await adapter.create_ticket(
            CreateTicketRequest(
                provider_contact_id="101",
                subject="Printer offline",
                initial_message="Receipt printer not responding",
                tags=["printer"],
                metadata={"source_id": "tablet-user-99"},
            ),
        )
        await adapter._client.close()
        assert ticket.tags == ["printer"]
        assert ticket.metadata["source_id"] == "tablet-user-99"
        assert any("/conversations/9001/messages" in path for path in paths)
        assert any(path.endswith("/labels") for path in paths)

    asyncio.run(_run())


def test_create_ticket_missing_inbox() -> None:
    async def _run() -> None:
        adapter = ChatwootAdapter(_settings(chatwoot_inbox_id=0))
        with pytest.raises(ChatwootConfigError, match="CHATWOOT_INBOX_ID"):
            await adapter.create_ticket(CreateTicketRequest(provider_contact_id="101"))

    asyncio.run(_run())


def test_create_ticket_invalid_contact_id() -> None:
    async def _run() -> None:
        transport = httpx.MockTransport(lambda _request: httpx.Response(200, json={}))
        adapter = ChatwootAdapter(_settings(), client=ChatwootClient(_settings(), transport=transport))
        with pytest.raises(ChatwootAPIError, match="Invalid provider_contact_id"):
            await adapter.create_ticket(CreateTicketRequest(provider_contact_id="not-a-number"))
        await adapter._client.close()

    asyncio.run(_run())
