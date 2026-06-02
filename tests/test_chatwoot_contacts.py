"""ChatwootAdapter get_or_create_contact tests — Task 1.3 sub-step 6."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from app.core.config import Settings
from app.models.standard import CreateContactRequest
from app.providers.ticketing.chatwoot.client import ChatwootClient
from app.providers.ticketing.chatwoot.errors import ChatwootAPIError, ChatwootConfigError
from app.providers.ticketing.chatwoot.mappers import contact_to_standard_contact
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


def _contact(contact_id: int = 101, **fields: object) -> dict:
    return {
        "id": contact_id,
        "name": fields.get("name", "Branch User"),
        "email": fields.get("email"),
        "phone_number": fields.get("phone"),
        "identifier": fields.get("identifier", "butterpos-user-99"),
    }


def test_contact_to_standard_contact_maps_fields() -> None:
    standard = contact_to_standard_contact(_contact(email="user@example.com", phone="+923001234567"))
    assert standard.provider_contact_id == "101"
    assert standard.email == "user@example.com"
    assert standard.phone == "+923001234567"
    assert standard.metadata["identifier"] == "butterpos-user-99"


def test_get_or_create_contact_returns_existing_from_filter() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("/contacts/filter"):
            return httpx.Response(200, json={"payload": [_contact()]})
        return httpx.Response(404)

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        adapter = ChatwootAdapter(_settings(), client=ChatwootClient(_settings(), transport=transport))
        contact = await adapter.get_or_create_contact(
            CreateContactRequest(
                name="Branch User",
                external_user_id="butterpos-user-99",
            ),
        )
        await adapter._client.close()
        assert contact.provider_contact_id == "101"
        assert any(path.endswith("/contacts/filter") for path in paths)
        assert not any(path.endswith("/contacts") and "filter" not in path for path in paths)

    asyncio.run(_run())


def test_get_or_create_contact_creates_when_missing() -> None:
    created = {"called": False}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/contacts/filter"):
            return httpx.Response(200, json={"payload": []})
        if request.url.path.endswith("/contacts/search"):
            return httpx.Response(200, json={"payload": []})
        if request.method == "POST" and request.url.path.endswith("/contacts"):
            created["called"] = True
            body = json.loads(request.content)
            assert body["inbox_id"] == 42
            assert body["identifier"] == "butterpos-user-77"
            return httpx.Response(200, json=_contact(contact_id=202, identifier="butterpos-user-77"))
        return httpx.Response(404)

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        adapter = ChatwootAdapter(_settings(), client=ChatwootClient(_settings(), transport=transport))
        contact = await adapter.get_or_create_contact(
            CreateContactRequest(
                name="New User",
                external_user_id="butterpos-user-77",
            ),
        )
        await adapter._client.close()
        assert created["called"] is True
        assert contact.provider_contact_id == "202"

    asyncio.run(_run())


def test_get_or_create_contact_requires_lookup_key() -> None:
    async def _run() -> None:
        adapter = ChatwootAdapter(_settings())
        with pytest.raises(ChatwootAPIError, match="external_user_id, email, or phone"):
            await adapter.get_or_create_contact(CreateContactRequest(name="No identifiers"))

    asyncio.run(_run())


def test_get_or_create_contact_requires_inbox() -> None:
    async def _run() -> None:
        adapter = ChatwootAdapter(_settings(chatwoot_inbox_id=0))
        with pytest.raises(ChatwootConfigError, match="CHATWOOT_INBOX_ID"):
            await adapter.get_or_create_contact(
                CreateContactRequest(external_user_id="butterpos-user-99"),
            )

    asyncio.run(_run())
