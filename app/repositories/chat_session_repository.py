"""Chat session persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.chat_session import ChatSession
from app.schemas.chat_session import StoredChatTurn


class ChatSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_external_id(self, external_id: str) -> ChatSession | None:
        return await self._session.scalar(
            select(ChatSession).where(ChatSession.external_id == external_id),
        )

    async def get_by_provider_ticket_id(self, provider_ticket_id: str) -> ChatSession | None:
        return await self._session.scalar(
            select(ChatSession).where(ChatSession.provider_ticket_id == provider_ticket_id),
        )

    async def get_for_subject(self, external_id: str, jwt_subject: str) -> ChatSession | None:
        row = await self.get_by_external_id(external_id)
        if row is None or row.jwt_subject != jwt_subject:
            return None
        return row

    async def get_or_create(
        self,
        *,
        external_id: str | None,
        jwt_subject: str,
        source: str,
        branch_id: str | None,
    ) -> ChatSession:
        resolved_id = external_id or str(uuid.uuid4())
        row = await self.get_by_external_id(resolved_id)
        if row is not None:
            return row

        row = ChatSession(
            external_id=resolved_id,
            jwt_subject=jwt_subject,
            source=source,
            branch_id=branch_id,
            status="active",
            messages_json=[],
            meta={},
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def append_turns(
        self,
        chat_session: ChatSession,
        turns: list[StoredChatTurn],
    ) -> None:
        messages = list(chat_session.messages_json or [])
        messages.extend(turn.model_dump(mode="json") for turn in turns)
        chat_session.messages_json = messages
        await self._session.flush()

    async def mark_escalated(
        self,
        chat_session: ChatSession,
        *,
        provider_ticket_id: str,
        provider_contact_id: str,
        reason: str,
    ) -> None:
        chat_session.status = "escalated"
        chat_session.provider_ticket_id = provider_ticket_id
        chat_session.provider_contact_id = provider_contact_id
        meta = dict(chat_session.meta or {})
        meta["escalation_reason"] = reason
        chat_session.meta = meta
        await self._session.flush()

    async def record_middleware_message_id(
        self,
        chat_session: ChatSession,
        provider_event_id: str,
    ) -> None:
        """Track middleware-originated Chatwoot messages to avoid relay echo."""
        meta = dict(chat_session.meta or {})
        ids = [str(x) for x in meta.get("middleware_message_ids") or []]
        if provider_event_id not in ids:
            ids.append(provider_event_id)
        meta["middleware_message_ids"] = ids[-50:]
        chat_session.meta = meta
        await self._session.flush()

    @staticmethod
    def known_provider_event_ids(chat_session: ChatSession) -> set[str]:
        ids = set(str(x) for x in (chat_session.meta or {}).get("middleware_message_ids") or [])
        for raw in chat_session.messages_json or []:
            turn = StoredChatTurn.model_validate(raw)
            if turn.provider_event_id:
                ids.add(turn.provider_event_id)
        return ids
