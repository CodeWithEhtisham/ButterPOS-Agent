"""Chatwoot list/filter and ticket cache polling tests — Task 1.4.4."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from app.core.config import Settings
from app.models.standard import StandardStatus, StandardTicket
from app.providers.ticketing.chatwoot.client import ChatwootClient
from app.providers.ticketing.chatwoot.conversations import list_conversations_updated_since
from app.providers.ticketing.chatwoot_adapter import ChatwootAdapter
from app.repositories.ticket_cache_repository import upsert_ticket_cache
from app.services.ticket_polling_service import TicketPollingService
from app.worker.polling_state import InMemoryPollingCursorStore
from app.worker.tasks import polling_tasks
from tests.support.ticket_cache_memory_session import TicketCacheMemorySession


def _settings(**overrides: object) -> Settings:
    base = {
        "_env_file": None,
        "chatwoot_base_url": "http://localhost:3000",
        "chatwoot_api_token": "test-token",
        "chatwoot_account_id": 1,
        "chatwoot_inbox_id": 42,
        "webhook_polling_initial_lookback_seconds": 900,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _ticket(ticket_id: str = "100", *, status: StandardStatus = StandardStatus.OPEN) -> StandardTicket:
    return StandardTicket(
        provider_ticket_id=ticket_id,
        status=status,
        subject="Printer issue",
        provider_contact_id="7",
        assignee_id="3",
        tags=["hardware"],
        updated_at=datetime(2026, 3, 4, 12, 0, tzinfo=UTC),
    )


def test_list_conversations_updated_since_paginates() -> None:
    page1 = {
        "data": {
            "payload": [{"id": 1, "status": "open", "inbox_id": 42, "updated_at": 1700000001}],
            "meta": {"total_pages": 2},
        }
    }
    page2 = {
        "data": {
            "payload": [{"id": 2, "status": "resolved", "inbox_id": 42, "updated_at": 1700000002}],
            "meta": {"total_pages": 2},
        }
    }
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body["page"])
        return httpx.Response(200, json=page1 if body["page"] == 1 else page2)

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        client = ChatwootClient(_settings(), transport=transport)
        since = datetime(2026, 3, 4, 0, 0, tzinfo=UTC)
        items = await list_conversations_updated_since(client, since)
        await client.close()
        assert len(items) == 2
        assert calls == [1, 2]

    asyncio.run(_run())


def test_adapter_list_tickets_updated_since() -> None:
    response = {
        "data": {
            "payload": [
                {
                    "id": 5678,
                    "status": "open",
                    "inbox_id": 42,
                    "updated_at": "2026-03-04T10:30:00Z",
                    "custom_attributes": {"subject": "Help"},
                }
            ],
            "meta": {"total_pages": 1},
        }
    }
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json=response))

    async def _run() -> None:
        adapter = ChatwootAdapter(_settings(), client=ChatwootClient(_settings(), transport=transport))
        tickets = await adapter.list_tickets_updated_since(datetime(2026, 3, 4, 0, 0, tzinfo=UTC))
        await adapter._client.close()
        assert len(tickets) == 1
        assert tickets[0].provider_ticket_id == "5678"
        assert tickets[0].subject == "Help"

    asyncio.run(_run())


def test_upsert_ticket_cache_create_and_update() -> None:
    async def _run() -> None:
        session = TicketCacheMemorySession()
        created = await upsert_ticket_cache(session, _ticket())
        assert created.action == "created"

        updated = await upsert_ticket_cache(
            session,
            _ticket(status=StandardStatus.RESOLVED),
        )
        assert updated.action == "updated"
        assert session.row("100").status == "resolved"

        unchanged = await upsert_ticket_cache(session, _ticket(status=StandardStatus.RESOLVED))
        assert unchanged.action == "unchanged"

    asyncio.run(_run())


def test_ticket_polling_service_reconciles() -> None:
    provider = MagicMock()
    provider.list_tickets_updated_since = AsyncMock(
        return_value=[_ticket(), _ticket("101", status=StandardStatus.PENDING)]
    )
    session = TicketCacheMemorySession()
    cursor = InMemoryPollingCursorStore()

    async def _run() -> None:
        service = TicketPollingService(
            provider,
            session,
            settings=_settings(),
            cursor_store=cursor,
        )
        result = await service.reconcile()
        assert result.fetched == 2
        assert result.created == 2
        assert cursor.get_last_sync() is not None
        provider.list_tickets_updated_since.assert_awaited_once()

    asyncio.run(_run())


def test_poll_reconcile_task_returns_summary() -> None:
    mock_result = MagicMock()
    mock_result.since = datetime(2026, 3, 4, 0, 0, tzinfo=UTC)
    mock_result.fetched = 1
    mock_result.created = 1
    mock_result.updated = 0
    mock_result.unchanged = 0

    async def _fake_reconcile(self: TicketPollingService) -> MagicMock:
        return mock_result

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(TicketPollingService, "reconcile", _fake_reconcile)
        mp.setattr(polling_tasks, "init_engine", lambda _settings: None)
        mp.setattr(polling_tasks, "shutdown_engine", AsyncMock())
        mp.setattr(
            polling_tasks,
            "create_ticketing_provider",
            lambda _settings: MagicMock(_client=MagicMock(close=AsyncMock())),
        )
        mp.setattr(
            polling_tasks,
            "get_session_factory",
            lambda: MagicMock(
                __aenter__=AsyncMock(return_value=MagicMock()),
                __aexit__=AsyncMock(return_value=False),
            ),
        )
        summary = polling_tasks.poll_ticket_reconcile_task()
    assert summary["fetched"] == 1
    assert summary["created"] == 1
