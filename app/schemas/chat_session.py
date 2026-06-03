"""Chat session persistence schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

ChatSessionStatus = Literal["active", "escalated"]
ChatSource = Literal["android", "hq", "test"]
ChatSpeaker = Literal["customer", "ai", "human"]


class StoredToolCall(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: str = ""
    success: bool = True


class StoredChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    tool_calls: list[StoredToolCall] = Field(default_factory=list)
    speaker: ChatSpeaker = "customer"
    provider_event_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def default_speaker(cls, data: Any) -> Any:
        if isinstance(data, dict) and "speaker" not in data:
            data = dict(data)
            data["speaker"] = "customer" if data.get("role") == "user" else "ai"
        return data


def turns_to_agent_history(turns: list[StoredChatTurn]) -> list[dict[str, str]]:
    """Map stored turns to AgentService history format."""
    return [{"role": t.role, "content": t.content} for t in turns[-20:]]
