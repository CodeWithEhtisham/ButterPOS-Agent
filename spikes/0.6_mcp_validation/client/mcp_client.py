"""MCP client layer — middleware talks to MCP server; never imports ButterPOS business logic."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

DEFAULT_STUB = (
    Path(__file__).resolve().parent.parent / "stub_server" / "butterpos_stub_mcp.py"
)


@dataclass
class MCPToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class MCPCallResult:
    tool_name: str
    arguments: dict[str, Any]
    content: str
    is_error: bool = False


@dataclass
class MCPClient:
    """Thin MCP client wrapper for stdio transport (Phase 0 spike)."""

    server_command: str = sys.executable
    server_args: list[str] = field(default_factory=list)
    tools: list[MCPToolSpec] = field(default_factory=list)

    @classmethod
    def for_stub(cls, stub_path: Path | None = None) -> MCPClient:
        path = stub_path or DEFAULT_STUB
        return cls(server_command=sys.executable, server_args=[str(path)])

    def llm_tools_format(self) -> list[dict[str, Any]]:
        """Convert MCP tool catalog to OpenAI-compatible function-calling schema (OpenRouter)."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            }
            for t in self.tools
        ]

    async def connect_and_list_tools(self) -> list[MCPToolSpec]:
        params = StdioServerParameters(
            command=self.server_command,
            args=self.server_args,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                self.tools = [
                    MCPToolSpec(
                        name=t.name,
                        description=t.description or "",
                        input_schema=t.inputSchema or {"type": "object", "properties": {}},
                    )
                    for t in result.tools
                ]
                return self.tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPCallResult:
        params = StdioServerParameters(
            command=self.server_command,
            args=self.server_args,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments=arguments)
                text_parts = [
                    c.text for c in result.content if hasattr(c, "text") and c.text
                ]
                return MCPCallResult(
                    tool_name=name,
                    arguments=arguments,
                    content="\n".join(text_parts) if text_parts else json.dumps({}),
                    is_error=bool(result.isError),
                )

    async def run_direct_probe(self) -> list[MCPCallResult]:
        """Call each expected tool once with sample args (no LLM)."""
        probes: list[tuple[str, dict[str, Any]]] = [
            ("get_system_info", {"device_id": "tablet-spike-01"}),
            ("check_printer", {"branch_id": "branch-101"}),
            ("get_sales", {"branch_id": "branch-101", "date": "2026-06-01"}),
            (
                "add_menu_item",
                {
                    "branch_id": "branch-101",
                    "name": "Spike Test Item",
                    "price": 99.0,
                    "category": "Test",
                },
            ),
        ]
        results: list[MCPCallResult] = []
        for name, args in probes:
            results.append(await self.call_tool(name, args))
        return results
