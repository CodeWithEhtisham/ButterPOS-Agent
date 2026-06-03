"""Chat orchestration — agent loop, Postgres history, Chatwoot escalation."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.standard import AddCustomerMessageRequest
from app.providers.ticketing.base import TicketingProvider
from app.repositories.chat_session_repository import ChatSessionRepository
from app.schemas.chat import ChatMessageRequest
from app.schemas.chat_session import (
    ChatSource,
    StoredChatTurn,
    StoredToolCall,
    turns_to_agent_history,
)
from app.services.agent_service import AgentRunResult, AgentService
from app.services.escalation_service import EscalationService, should_auto_escalate

class ChatRunResult:
    """Outcome of one chat message handled by middleware."""

    def __init__(
        self,
        *,
        agent: AgentRunResult,
        conversation_id: str,
        escalated: bool = False,
        provider_ticket_id: str | None = None,
        escalation_reason: str | None = None,
        forwarded_to_human: bool = False,
    ) -> None:
        self.agent = agent
        self.conversation_id = conversation_id
        self.escalated = escalated
        self.provider_ticket_id = provider_ticket_id
        self.escalation_reason = escalation_reason
        self.forwarded_to_human = forwarded_to_human


class ChatService:
    def __init__(
        self,
        settings: Settings,
        agent: AgentService,
        ticketing: TicketingProvider,
    ) -> None:
        self._settings = settings
        self._agent = agent
        self._ticketing = ticketing
        self._escalation = EscalationService(settings, ticketing)

    async def handle_message(
        self,
        db: AsyncSession,
        body: ChatMessageRequest,
        *,
        jwt_subject: str,
    ) -> ChatRunResult:
        repo = ChatSessionRepository(db)
        source: ChatSource = body.source or "test"

        chat_session = await repo.get_or_create(
            external_id=body.conversation_id,
            jwt_subject=jwt_subject,
            source=source,
            branch_id=body.branch_id,
        )

        if chat_session.status == "escalated" and chat_session.provider_ticket_id:
            return await self._forward_to_human_agent(db, repo, chat_session, body)

        if chat_session.messages_json:
            history = turns_to_agent_history(
                [StoredChatTurn.model_validate(m) for m in chat_session.messages_json],
            )
        else:
            history = [turn.model_dump() for turn in body.history]

        agent_result = await self._agent.run_chat(
            body.message,
            history=history,
            branch_id=body.branch_id,
        )

        tool_records = [
            StoredToolCall(
                tool_name=tc.tool_name,
                arguments=tc.arguments,
                result=tc.result,
                success=tc.success,
            )
            for tc in agent_result.tool_calls
        ]

        await repo.append_turns(
            chat_session,
            [
                StoredChatTurn(
                    role="user",
                    content=body.message,
                    at=datetime.now(tz=UTC),
                    speaker="customer",
                ),
                StoredChatTurn(
                    role="assistant",
                    content=agent_result.reply or agent_result.error or "",
                    at=datetime.now(tz=UTC),
                    tool_calls=tool_records,
                    speaker="ai",
                ),
            ],
        )

        escalated = False
        ticket_id: str | None = chat_session.provider_ticket_id
        escalation_reason: str | None = None

        wants_escalation = body.escalate or should_auto_escalate(
            body.message,
            agent_error=agent_result.error,
        )

        if wants_escalation and chat_session.status != "escalated":
            escalation_reason = _escalation_reason(body.escalate, agent_result.error)
            escalation = await self._escalation.escalate_to_chatwoot(
                db,
                chat_session,
                reason=escalation_reason,
                customer_reply=agent_result.reply if agent_result.reply else None,
            )
            ticket_id = escalation.provider_ticket_id
            await repo.mark_escalated(
                chat_session,
                provider_ticket_id=ticket_id,
                provider_contact_id=escalation.provider_contact_id,
                reason=escalation_reason,
            )
            escalated = True
            if agent_result.reply and "escalated" not in agent_result.reply.lower():
                agent_result.reply = (
                    f"{agent_result.reply}\n\n"
                    "I've connected you with a human support agent in Chatwoot."
                )

        return ChatRunResult(
            agent=agent_result,
            conversation_id=chat_session.external_id,
            escalated=escalated,
            provider_ticket_id=ticket_id,
            escalation_reason=escalation_reason,
        )

    async def get_session_for_subject(
        self,
        db: AsyncSession,
        conversation_id: str,
        *,
        jwt_subject: str,
    ):
        repo = ChatSessionRepository(db)
        return await repo.get_for_subject(conversation_id, jwt_subject)

    async def _forward_to_human_agent(
        self,
        db: AsyncSession,
        repo: ChatSessionRepository,
        chat_session,
        body: ChatMessageRequest,
    ) -> ChatRunResult:
        ticket_id = chat_session.provider_ticket_id
        assert ticket_id is not None

        await repo.append_turns(
            chat_session,
            [
                StoredChatTurn(
                    role="user",
                    content=body.message,
                    at=datetime.now(tz=UTC),
                    speaker="customer",
                ),
            ],
        )

        msg_id = await self._ticketing.add_customer_message(
            AddCustomerMessageRequest(provider_ticket_id=ticket_id, body=body.message),
        )
        if msg_id:
            await repo.record_middleware_message_id(chat_session, msg_id)

        # Empty reply — UI shows a persistent "human agent active" state instead of a bubble per send.
        agent_result = AgentRunResult(
            reply="",
            model=self._settings.llm_primary_model,
        )
        return ChatRunResult(
            agent=agent_result,
            conversation_id=chat_session.external_id,
            escalated=True,
            provider_ticket_id=ticket_id,
            forwarded_to_human=True,
        )


def _escalation_reason(forced: bool, agent_error: str | None) -> str:
    if forced:
        return "client_requested_escalation"
    if agent_error:
        return f"agent_error:{agent_error[:120]}"
    return "customer_requested_human"
