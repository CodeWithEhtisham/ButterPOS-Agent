"""AI conversation persistence — ticket-bound agent memory."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ai_conversation import AIConversation
from app.schemas.chat_session import StoredChatTurn


class AIConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_ticket_cache_id(self, ticket_cache_id: int) -> AIConversation | None:
        return await self._session.scalar(
            select(AIConversation).where(AIConversation.ticket_cache_id == ticket_cache_id),
        )

    async def get_or_create(
        self,
        *,
        ticket_cache_id: int,
        user_id: int | None = None,
    ) -> AIConversation:
        row = await self.get_by_ticket_cache_id(ticket_cache_id)
        if row is not None:
            return row

        row = AIConversation(
            ticket_cache_id=ticket_cache_id,
            user_id=user_id,
            messages_json=[],
            confidence_history=[],
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def append_turns(
        self,
        conversation: AIConversation,
        turns: list[StoredChatTurn],
    ) -> None:
        messages = list(conversation.messages_json or [])
        messages.extend(turn.model_dump(mode="json") for turn in turns)
        conversation.messages_json = messages
        await self._session.flush()
