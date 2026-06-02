"""ChatwootAdapter add_comment / add_note tests — Task 1.3 sub-step 4."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from app.core.config import Settings
from app.models.standard import AddCommentRequest, AddNoteRequest
from app.providers.ticketing.chatwoot.client import ChatwootClient
from app.providers.ticketing.chatwoot.errors import ChatwootAPIError
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


def test_add_comment_posts_public_message() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": 55})

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        adapter = ChatwootAdapter(_settings(), client=ChatwootClient(_settings(), transport=transport))
        await adapter.add_comment(
            AddCommentRequest(
                provider_ticket_id="9001",
                body="Try restarting the receipt printer.",
            ),
        )
        await adapter._client.close()

    asyncio.run(_run())
    assert captured["body"]["content"] == "Try restarting the receipt printer."
    assert captured["body"]["private"] is False
    assert captured["body"]["message_type"] == "outgoing"


def test_add_comment_supports_rich_content_metadata() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": 56})

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        adapter = ChatwootAdapter(_settings(), client=ChatwootClient(_settings(), transport=transport))
        await adapter.add_comment(
            AddCommentRequest(
                provider_ticket_id="9001",
                body="Select an option",
                metadata={
                    "content_type": "input_select",
                    "content_attributes": {
                        "items": [{"title": "Restart printer", "value": "restart"}],
                    },
                },
            ),
        )
        await adapter._client.close()

    asyncio.run(_run())
    assert captured["body"]["content_type"] == "input_select"
    assert captured["body"]["content_attributes"]["items"][0]["value"] == "restart"


def test_add_note_posts_private_message() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": 57})

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        adapter = ChatwootAdapter(_settings(), client=ChatwootClient(_settings(), transport=transport))
        await adapter.add_note(
            AddNoteRequest(
                provider_ticket_id="9001",
                body="Escalated: billing API timeout during sync check.",
            ),
        )
        await adapter._client.close()

    asyncio.run(_run())
    assert captured["body"]["private"] is True
    assert captured["body"]["content_type"] == "text"


def test_add_comment_invalid_ticket_id() -> None:
    async def _run() -> None:
        adapter = ChatwootAdapter(_settings())
        with pytest.raises(ChatwootAPIError, match="Invalid provider_ticket_id"):
            await adapter.add_comment(
                AddCommentRequest(provider_ticket_id="bad-id", body="hello"),
            )

    asyncio.run(_run())
