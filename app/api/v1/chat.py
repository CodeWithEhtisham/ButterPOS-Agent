"""Chat routes — frontend (React / Kotlin widget) ↔ middleware."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_subject, pii_masker_dep, settings_dep, ticketing_provider_dep
from app.core.config import Settings
from app.core.mcp.factory import get_mcp_client
from app.core.pii.masker import PIIMasker
from app.db.session import get_async_session
from app.providers.llm.factory import get_llm_provider
from app.providers.ticketing.base import TicketingProvider
from app.schemas.auth import AuthenticatedSubject
from app.schemas.chat import (
    ChatHealthResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionResponse,
    ChatToolCallOut,
    ChatTurnOut,
)
from app.schemas.chat_session import StoredChatTurn
from app.services.agent_service import AgentService
from app.services.chat_service import ChatService
from app.services.chat_session_sync_service import ChatSessionSyncService
from app.providers.ticketing.factory import create_ticketing_provider

router = APIRouter(prefix="/chat", tags=["chat"])

_UI_STATIC = Path(__file__).resolve().parents[2] / "static" / "chat-test"
_UI_ASSETS: dict[str, str] = {
    "style.css": "text/css; charset=utf-8",
    "app.js": "application/javascript; charset=utf-8",
}


def _chat_service(
    settings: Annotated[Settings, Depends(settings_dep)],
    pii: Annotated[PIIMasker, Depends(pii_masker_dep)],
    ticketing: Annotated[TicketingProvider, Depends(ticketing_provider_dep)],
) -> ChatService:
    agent = AgentService(settings, get_llm_provider(), get_mcp_client(), pii)
    return ChatService(settings, agent, ticketing)


@router.get(
    "/health",
    response_model=ChatHealthResponse,
    summary="Chat + MCP readiness",
)
async def chat_health(
    settings: Annotated[Settings, Depends(settings_dep)],
) -> ChatHealthResponse:
    """Unauthenticated probe — remote MCP connected and OpenRouter configured."""
    try:
        mcp = get_mcp_client()
        tool_count = len(mcp.tools)
    except RuntimeError:
        tool_count = 0

    openrouter_ok = bool(settings.openrouter_api_key.strip())
    mcp_url = settings.mcp_server_url.strip()
    return ChatHealthResponse(
        ready=tool_count > 0 and openrouter_ok and bool(mcp_url),
        mcp_tools=tool_count,
        mcp_server_url=mcp_url,
        mcp_transport=settings.mcp_transport,
        model=settings.llm_primary_model,
        openrouter_configured=openrouter_ok,
    )


@router.get("/ui", include_in_schema=False)
async def chat_test_ui() -> FileResponse:
    """Local HTML chat UI for manual testing (same API as production React frontend)."""
    return FileResponse(_UI_STATIC / "index.html")


@router.get("/ui/static/{asset}", include_in_schema=False)
async def chat_ui_static(asset: str) -> FileResponse:
    """Serve chat test UI assets."""
    media_type = _UI_ASSETS.get(asset)
    if media_type is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    path = (_UI_STATIC / asset).resolve()
    if not path.is_file() or _UI_STATIC.resolve() not in path.parents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return FileResponse(path, media_type=media_type)


@router.post(
    "/messages",
    response_model=ChatMessageResponse,
    summary="Send chat message (LLM + remote MCP tools)",
)
async def send_chat_message(
    body: ChatMessageRequest,
    subject: Annotated[AuthenticatedSubject, Depends(get_current_subject)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[ChatService, Depends(_chat_service)],
) -> ChatMessageResponse:
    """JWT-protected chat — persisted in Postgres; escalates to Chatwoot when requested."""
    run = await service.handle_message(db, body, jwt_subject=subject.subject)
    agent = run.agent

    if agent.error and not agent.reply:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=agent.error)

    return ChatMessageResponse(
        reply=agent.reply,
        model=agent.model,
        pii_tokens_masked=agent.pii_tokens_masked,
        error=agent.error,
        conversation_id=run.conversation_id,
        escalated=run.escalated,
        provider_ticket_id=run.provider_ticket_id,
        escalation_reason=run.escalation_reason,
        forwarded_to_human=run.forwarded_to_human,
        message_count=None,
        tool_calls=[
            ChatToolCallOut(
                tool_name=tc.tool_name,
                arguments=tc.arguments,
                result=tc.result,
                success=tc.success,
            )
            for tc in agent.tool_calls
        ],
    )


@router.get(
    "/sessions/{conversation_id}",
    response_model=ChatSessionResponse,
    summary="Poll chat session (human agent replies after escalation)",
)
async def get_chat_session(
    conversation_id: str,
    subject: Annotated[AuthenticatedSubject, Depends(get_current_subject)],
    settings: Annotated[Settings, Depends(settings_dep)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[ChatService, Depends(_chat_service)],
    since_index: int = 0,
) -> ChatSessionResponse:
    """JWT-protected session poll — returns new messages including human agent replies relayed from Chatwoot."""
    chat_session = await service.get_session_for_subject(
        db,
        conversation_id,
        jwt_subject=subject.subject,
    )
    if chat_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    sync = ChatSessionSyncService(settings, create_ticketing_provider(settings))
    await sync.sync_human_replies_from_chatwoot(db, chat_session)

    turns = [StoredChatTurn.model_validate(m) for m in chat_session.messages_json or []]
    sliced = turns[since_index:] if since_index > 0 else turns
    return ChatSessionResponse(
        conversation_id=chat_session.external_id,
        status=chat_session.status,
        provider_ticket_id=chat_session.provider_ticket_id,
        message_count=len(turns),
        messages=[
            ChatTurnOut(
                role=turn.role,
                content=turn.content,
                speaker=turn.speaker,
                at=turn.at,
            )
            for turn in sliced
        ],
    )
