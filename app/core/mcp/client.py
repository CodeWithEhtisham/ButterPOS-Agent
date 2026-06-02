"""MCP client — middleware connects to a remote MCP server by URL."""

from __future__ import annotations

import json
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any, Literal

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client

MCPTransport = Literal["streamable_http", "sse"]


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
    server_url: str = ""
    transport: MCPTransport = "streamable_http"
    tools: list[MCPToolSpec] = field(default_factory=list)
    _stack: AsyncExitStack | None = field(default=None, repr=False)
    _session: ClientSession | None = field(default=None, repr=False)

    @classmethod
    def for_url(cls, url: str, *, transport: MCPTransport = "streamable_http") -> MCPClient:
        return cls(server_url=url.rstrip("/"), transport=transport)

    @property
    def connected(self) -> bool:
        return self._session is not None

    def llm_tools_format(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            }
            for tool in self.tools
        ]

    async def connect(self) -> list[MCPToolSpec]:
        """Open a persistent session to the remote MCP server and cache tools."""
        if not self.server_url.strip():
            raise ValueError("MCP server URL is not configured")

        await self.disconnect()
        stack = AsyncExitStack()
        try:
            if self.transport == "sse":
                read, write = await stack.enter_async_context(sse_client(self.server_url))
            else:
                read, write, _ = await stack.enter_async_context(
                    streamable_http_client(self.server_url),
                )

            session = await stack.enter_async_context(ClientSession(read, write))
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
            self._stack = stack
            self._session = session
            return self.tools
        except Exception:
            await stack.aclose()
            raise

    async def disconnect(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._session = None

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPCallResult:
        if self._session is None:
            raise RuntimeError("MCP client is not connected — check MCP_SERVER_URL and lifespan")

        result = await self._session.call_tool(name, arguments=arguments)
        text_parts = [c.text for c in result.content if hasattr(c, "text") and c.text]
        return MCPCallResult(
            tool_name=name,
            arguments=arguments,
            content="\n".join(text_parts) if text_parts else json.dumps({}),
            is_error=bool(result.isError),
        )
