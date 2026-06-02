"""Chat API schemas — frontend ↔ middleware contract."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


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
        description="Optional client-side conversation id for correlation",
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


class ChatHealthResponse(BaseModel):
    ready: bool
    mcp_tools: int
    mcp_server_url: str
    mcp_transport: str
    model: str
    openrouter_configured: bool
