"""Chat API schemas — frontend ↔ middleware contract."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ChatSource = Literal["android", "hq", "test"]
ChatSpeaker = Literal["customer", "ai", "human"]


class ChatHistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatMessageRequest(BaseModel):
    """POST /api/v1/chat/messages — React widget / tablet app."""

    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatHistoryTurn] = Field(default_factory=list)
    branch_id: str | None = Field(
        default=None,
        description="Override default branch for MCP tool calls",
    )
    conversation_id: str | None = Field(
        default=None,
        description="Client session id — server creates UUID if omitted",
    )
    source: ChatSource = Field(
        default="test",
        description="Client origin: android tablet, HQ admin, or test UI",
    )
    escalate: bool = Field(
        default=False,
        description="Force escalation to Chatwoot human agent after this turn",
    )


class ChatToolCallOut(BaseModel):
    tool_name: str
    arguments: dict[str, object]
    result: str
    success: bool


class ChatMessageResponse(BaseModel):
    reply: str
    model: str
    tool_calls: list[ChatToolCallOut] = Field(default_factory=list)
    pii_tokens_masked: int = 0
    error: str | None = None
    conversation_id: str | None = None
    escalated: bool = False
    provider_ticket_id: str | None = None
    escalation_reason: str | None = None
    forwarded_to_human: bool = False
    message_count: int | None = None


class ChatTurnOut(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    speaker: ChatSpeaker
    at: datetime


class ChatSessionResponse(BaseModel):
    conversation_id: str
    status: str
    provider_ticket_id: str | None = None
    message_count: int
    messages: list[ChatTurnOut] = Field(default_factory=list)


class ChatHealthResponse(BaseModel):
    ready: bool
    mcp_tools: int
    mcp_server_url: str
    mcp_transport: str
    model: str
    openrouter_configured: bool
