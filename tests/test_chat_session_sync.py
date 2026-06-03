"""Chat session sync from Chatwoot — poll fallback when webhooks missing."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings
from app.db.models.chat_session import ChatSession
from app.providers.ticketing.chatwoot_adapter import ChatwootAdapter
from app.services.chat_session_sync_service import ChatSessionSyncService


def test_sync_appends_outgoing_human_message() -> None:
    async def _run() -> None:
        settings = Settings(_env_file=None)
        adapter = MagicMock(spec=ChatwootAdapter)
        adapter._client = MagicMock()
        adapter.provider_name = "chatwoot"

        ticketing = MagicMock()
        ticketing.inner = adapter

        session = ChatSession(
            external_id="sess-1",
            jwt_subject="staff-1",
            source="test",
            status="escalated",
            provider_ticket_id="99",
            messages_json=[],
            meta={},
        )

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.services.chat_session_sync_service._unwrap_chatwoot",
                lambda _p: adapter,
            )
            mp.setattr(
                "app.services.chat_session_sync_service.list_conversation_messages",
                AsyncMock(
                    return_value=[
                        {
                            "id": 501,
                            "content": "On it — checking your printer now.",
                            "message_type": "outgoing",
                            "private": False,
                            "created_at": datetime.now(tz=UTC).timestamp(),
                            "sender": {"id": 2, "type": "user", "name": "Agent"},
                        },
                    ],
                ),
            )
            append = AsyncMock()
            mp.setattr(
                "app.services.chat_session_sync_service.ChatSessionRepository.append_turns",
                append,
            )

            added = await ChatSessionSyncService(settings, ticketing).sync_human_replies_from_chatwoot(
                AsyncMock(),
                session,
            )

        assert added == 1
        append.assert_awaited_once()

    asyncio.run(_run())
