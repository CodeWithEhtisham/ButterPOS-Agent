"""ChatwootAdapter assign_agent / add_tags tests — Task 1.3 sub-step 5."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from app.core.config import Settings
from app.models.standard import AddTagsRequest, AssignAgentRequest
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


def _conversation(*, labels: list[str] | None = None, assignee_id: int | None = None) -> dict:
    body: dict = {
        "id": 9001,
        "status": "open",
        "contact": {"id": 101},
        "labels": labels or ["network"],
    }
    if assignee_id is not None:
        body["assignee"] = {"id": assignee_id}
    return body


def test_assign_agent_posts_assignment_and_returns_ticket() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/assignments"):
            captured["assignment"] = json.loads(request.content)
            return httpx.Response(200, json={"id": 34, "name": "Agent"})
        if request.method == "GET" and request.url.path.endswith("/conversations/9001"):
            return httpx.Response(200, json=_conversation(assignee_id=34))
        return httpx.Response(404)

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        adapter = ChatwootAdapter(_settings(), client=ChatwootClient(_settings(), transport=transport))
        ticket = await adapter.assign_agent(
            AssignAgentRequest(provider_ticket_id="9001", assignee_id="34"),
        )
        await adapter._client.close()
        assert captured["assignment"] == {"assignee_id": 34}
        assert ticket.assignee_id == "34"

    asyncio.run(_run())


def test_add_tags_merges_with_existing_labels() -> None:
    label_payloads: list[list[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path.endswith("/conversations/9001"):
            return httpx.Response(200, json=_conversation(labels=["network"]))
        if request.method == "POST" and request.url.path.endswith("/labels"):
            body = json.loads(request.content)
            label_payloads.append(body["labels"])
            return httpx.Response(200, json={"payload": body["labels"]})
        return httpx.Response(404)

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        adapter = ChatwootAdapter(_settings(), client=ChatwootClient(_settings(), transport=transport))
        ticket = await adapter.add_tags(
            AddTagsRequest(provider_ticket_id="9001", tags=["printer", "network"]),
        )
        await adapter._client.close()
        assert label_payloads == [["network", "printer"]]
        assert ticket.tags == ["network", "printer"]

    asyncio.run(_run())


def test_assign_agent_invalid_assignee_id() -> None:
    async def _run() -> None:
        adapter = ChatwootAdapter(_settings())
        with pytest.raises(ChatwootAPIError, match="Invalid assignee_id"):
            await adapter.assign_agent(
                AssignAgentRequest(provider_ticket_id="9001", assignee_id="not-numeric"),
            )

    asyncio.run(_run())
