"""Chat API tests — frontend ↔ middleware contract."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.mcp.client import MCPCallResult, MCPToolSpec
from app.core.mcp.factory import clear_mcp_client_cache
from app.db.session import clear_session_cache, init_engine, shutdown_engine
from app.main import create_app
from app.providers.llm.base import LLMResponse
from app.providers.llm.factory import clear_llm_provider_cache
from app.services.agent_service import AgentRunResult, AgentToolCallRecord
from app.services.chat_service import ChatRunResult
from tests.test_auth import TEST_CLIENT_ID, TEST_CLIENT_SECRET


@pytest.fixture
def chat_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    get_settings.cache_clear()
    clear_session_cache()
    clear_mcp_client_cache()
    clear_llm_provider_cache()

    mock_mcp = MagicMock()
    mock_mcp.tools = [
        MCPToolSpec("search_menu_items", "search", {"type": "object", "properties": {}}),
    ]
    mock_mcp.connected = True
    mock_mcp.llm_tools_format.return_value = [{"type": "function", "function": {"name": "search_menu_items"}}]
    mock_mcp.call_tool = AsyncMock(
        return_value=MCPCallResult(
            tool_name="search_menu_items",
            arguments={"query": "biryani"},
            content='{"count": 1}',
        ),
    )

    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(
        side_effect=[
            LLMResponse(
                content="",
                model="test",
                latency_ms=1.0,
                raw={
                    "tool_calls": [
                        {
                            "id": "tc1",
                            "function": {
                                "name": "search_menu_items",
                                "arguments": '{"branch_id": "demo-branch-karachi", "query": "biryani"}',
                            },
                        },
                    ],
                },
            ),
            LLMResponse(content="Biryani is 450 PKR.", model="test", latency_ms=1.0, raw={}),
        ],
    )

    monkeypatch.setattr("app.core.mcp.factory._mcp_client", mock_mcp)
    monkeypatch.setattr("app.api.v1.chat.get_mcp_client", lambda: mock_mcp)
    monkeypatch.setattr("app.providers.llm.factory.get_llm_provider", lambda: mock_llm)
    monkeypatch.setattr("app.api.v1.chat.get_llm_provider", lambda: mock_llm)

    async def _fake_handle_message(
        _self: object,
        _db: object,
        body: object,
        *,
        jwt_subject: str,
    ) -> ChatRunResult:
        return ChatRunResult(
            agent=AgentRunResult(
                reply="Biryani is 450 PKR.",
                model="test",
                tool_calls=[
                    AgentToolCallRecord(
                        tool_name="search_menu_items",
                        arguments={"query": "biryani"},
                        result='{"count": 1}',
                        success=True,
                    ),
                ],
            ),
            conversation_id=getattr(body, "conversation_id", None) or "conv-1",
        )

    monkeypatch.setattr(
        "app.services.chat_service.ChatService.handle_message",
        _fake_handle_message,
    )

    settings = Settings(
        _env_file=None,
        jwt_secret="test-jwt-secret-at-least-32-characters-long",
        api_client_id=TEST_CLIENT_ID,
        api_client_secret=TEST_CLIENT_SECRET,
        openrouter_api_key="sk-test",
        mcp_server_url="http://127.0.0.1:3001/mcp",
    )
    get_settings.cache_clear()
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.deps.get_settings", lambda: settings)
    init_engine(settings)
    client = TestClient(create_app(settings))
    yield client
    asyncio.run(shutdown_engine())
    clear_session_cache()
    get_settings.cache_clear()


def _token(client: TestClient) -> str:
    res = client.post(
        "/api/v1/auth/token",
        json={
            "client_id": TEST_CLIENT_ID,
            "client_secret": TEST_CLIENT_SECRET,
            "subject": "staff-1",
        },
    )
    return res.json()["access_token"]


def test_chat_health(chat_client: TestClient) -> None:
    res = chat_client.get("/api/v1/chat/health")
    assert res.status_code == 200
    body = res.json()
    assert body["mcp_tools"] == 1
    assert body["mcp_server_url"] == "http://127.0.0.1:3001/mcp"
    assert body["openrouter_configured"] is True


def test_chat_test_ui(chat_client: TestClient) -> None:
    res = chat_client.get("/api/v1/chat/ui")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert "ButterPOS Chat Test" in res.text


def test_chat_messages_requires_jwt(chat_client: TestClient) -> None:
    res = chat_client.post("/api/v1/chat/messages", json={"message": "hi"})
    assert res.status_code == 401


def test_chat_messages_runs_mcp_tools(chat_client: TestClient) -> None:
    token = _token(chat_client)
    res = chat_client.post(
        "/api/v1/chat/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "What is biryani price?", "conversation_id": "conv-1"},
    )
    assert res.status_code == 200
    body = res.json()
    assert "Biryani" in body["reply"]
    assert body["conversation_id"] == "conv-1"
    assert len(body["tool_calls"]) == 1
    assert body["tool_calls"][0]["tool_name"] == "search_menu_items"
