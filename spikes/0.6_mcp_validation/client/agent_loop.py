"""Agent loop: LLMProvider + MCP client tool execution (Step 0.6 spike)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from providers.base import LLMProvider, LLMRequest

from client.mcp_client import MCPClient


@dataclass
class ToolCallRecord:
    model: str
    tool_name: str
    arguments: dict[str, Any]
    result_preview: str
    success: bool


@dataclass
class AgentLoopResult:
    model: str
    user_query: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    final_content: str = ""
    error: str | None = None


async def run_agent_loop(
    llm: LLMProvider,
    mcp: MCPClient,
    *,
    model: str,
    user_query: str,
    max_rounds: int = 3,
) -> AgentLoopResult:
    """
    Single-turn+tool loop: LLM selects MCP tools; client executes via MCP protocol.
    Same MCP tool catalog works regardless of model — portability test for D-4.
    """
    result = AgentLoopResult(model=model, user_query=user_query)
    tools = mcp.llm_tools_format()
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You are ButterPOS support AI. Use MCP tools to diagnose POS issues. "
                "Always call the appropriate tool before answering. Be concise."
            ),
        },
        {"role": "user", "content": user_query},
    ]

    for _ in range(max_rounds):
        response = await llm.complete(
            LLMRequest(messages=messages, model=model, tools=tools, max_tokens=512)
        )
        tool_calls = (response.raw or {}).get("tool_calls") or []

        if not tool_calls:
            result.final_content = response.content
            return result

        # Append assistant message with tool calls (OpenAI-compatible format)
        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "content": response.content or None,
            "tool_calls": tool_calls,
        }
        messages.append(assistant_msg)

        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}

            mcp_result = await mcp.call_tool(name, args)
            preview = mcp_result.content[:300]
            result.tool_calls.append(
                ToolCallRecord(
                    model=model,
                    tool_name=name,
                    arguments=args,
                    result_preview=preview,
                    success=not mcp_result.is_error,
                )
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id", name),
                    "content": mcp_result.content,
                }
            )

    result.error = "Max tool rounds exceeded without final answer"
    return result
