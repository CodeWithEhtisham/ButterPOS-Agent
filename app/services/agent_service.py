"""Support agent loop — LLM + MCP with mandatory PII masking."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.core.config import Settings
from app.core.mcp.client import MCPClient
from app.core.pii.masker import PIIMasker
from app.providers.llm.base import LLMProvider, LLMRequest


@dataclass
class AgentToolCallRecord:
    tool_name: str
    arguments: dict[str, Any]
    result: str
    success: bool


@dataclass
class AgentRunResult:
    reply: str
    tool_calls: list[AgentToolCallRecord] = field(default_factory=list)
    model: str = ""
    pii_tokens_masked: int = 0
    error: str | None = None


SYSTEM_PROMPT = """You are ButterPOS AI support for restaurant POS operators.

You have MCP tools to read and change menu items, taxes, printer status, and sales.
Always use tools to look up facts before answering — never invent menu prices.

Default branch_id: {branch_id}

Guidelines:
- Price questions → search_menu_items or list_menu_items / get_menu_item
- Create or update items → create_menu_item / update_menu_item
- Tax changes → set_item_tax or set_branch_tax
- Printer issues → check_printer first, then fix_printer when appropriate
- Be concise; confirm write operations after executing them
"""


class AgentService:
    """Runs the tool-calling agent loop through middleware providers."""

    def __init__(
        self,
        settings: Settings,
        llm: LLMProvider,
        mcp: MCPClient,
        pii_masker: PIIMasker,
    ) -> None:
        self._settings = settings
        self._llm = llm
        self._mcp = mcp
        self._pii = pii_masker

    async def run_chat(
        self,
        user_message: str,
        *,
        history: list[dict[str, str]] | None = None,
        branch_id: str | None = None,
    ) -> AgentRunResult:
        if not self._settings.openrouter_api_key.strip():
            return AgentRunResult(reply="", error="OPENROUTER_API_KEY is not configured")

        if not self._mcp.tools:
            if not self._mcp.connected:
                return AgentRunResult(
                    reply="",
                    error="MCP server not connected — set MCP_SERVER_URL and ensure the server is running",
                )
            return AgentRunResult(reply="", error="MCP server returned no tools")

        branch = branch_id or self._settings.agent_default_branch_id
        tools = self._mcp.llm_tools_format()
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT.format(branch_id=branch)},
        ]

        total_pii = 0
        if history:
            for turn in history[-10:]:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if role in {"user", "assistant"} and content:
                    masked = await self._pii.mask(content)
                    total_pii += masked.token_count
                    messages.append({"role": role, "content": masked.masked_text})

        user_mask = await self._pii.mask(user_message)
        total_pii += user_mask.token_count
        messages.append({"role": "user", "content": user_mask.masked_text})

        result = AgentRunResult(reply="", model=self._settings.llm_primary_model)
        result.pii_tokens_masked = total_pii
        last_content = ""

        for _ in range(self._settings.agent_max_tool_rounds):
            llm_messages, round_pii = await self._pii.mask_messages(messages)
            total_pii += round_pii
            result.pii_tokens_masked = total_pii

            response = await self._llm.complete(
                LLMRequest(
                    messages=llm_messages,
                    model=self._settings.llm_primary_model,
                    tools=tools,
                ),
            )
            tool_calls = response.raw.get("tool_calls") or []
            last_content = response.content or ""

            if not tool_calls:
                result.reply = await self._pii.unmask(last_content.strip() or "Done.")
                return result

            messages.append(
                {
                    "role": "assistant",
                    "content": response.content or None,
                    "tool_calls": tool_calls,
                },
            )

            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}

                if "branch_id" not in args and name not in {
                    "get_menu_item",
                    "update_menu_item",
                    "set_item_tax",
                }:
                    args.setdefault("branch_id", branch)

                mcp_result = await self._mcp.call_tool(name, args)
                result.tool_calls.append(
                    AgentToolCallRecord(
                        tool_name=name,
                        arguments=args,
                        result=mcp_result.content[:2000],
                        success=not mcp_result.is_error,
                    ),
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.get("id", name),
                        "content": mcp_result.content,
                    },
                )

        result.error = "Max tool rounds reached without a final answer"
        result.reply = await self._pii.unmask(last_content.strip())
        return result
