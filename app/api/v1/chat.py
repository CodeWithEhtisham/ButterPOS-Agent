"""Chat routes — frontend (React / Kotlin widget) ↔ middleware."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.api.deps import get_current_subject, pii_masker_dep, settings_dep
from app.core.config import Settings
from app.core.mcp.factory import get_mcp_client
from app.core.pii.masker import PIIMasker
from app.providers.llm.factory import get_llm_provider
from app.schemas.auth import AuthenticatedSubject
from app.schemas.chat import (
    ChatHealthResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatToolCallOut,
)
from app.services.agent_service import AgentService

router = APIRouter(prefix="/chat", tags=["chat"])

_UI_STATIC = Path(__file__).resolve().parents[2] / "static" / "chat-test"
_UI_ASSETS: dict[str, str] = {
    "style.css": "text/css; charset=utf-8",
    "app.js": "application/javascript; charset=utf-8",
}


def _agent_service(
    settings: Annotated[Settings, Depends(settings_dep)],
    pii: Annotated[PIIMasker, Depends(pii_masker_dep)],
) -> AgentService:
    return AgentService(settings, get_llm_provider(), get_mcp_client(), pii)


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
    _subject: Annotated[AuthenticatedSubject, Depends(get_current_subject)],
    service: Annotated[AgentService, Depends(_agent_service)],
) -> ChatMessageResponse:
    """JWT-protected chat — PII masked before every LLM call; tools via MCP_SERVER_URL."""
    result = await service.run_chat(
        body.message,
        history=[turn.model_dump() for turn in body.history],
        branch_id=body.branch_id,
    )

    if result.error and not result.reply:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.error)

    return ChatMessageResponse(
        reply=result.reply,
        model=result.model,
        pii_tokens_masked=result.pii_tokens_masked,
        error=result.error,
        conversation_id=body.conversation_id,
        tool_calls=[
            ChatToolCallOut(
                tool_name=tc.tool_name,
                arguments=tc.arguments,
                result=tc.result,
                success=tc.success,
            )
            for tc in result.tool_calls
        ],
    )
