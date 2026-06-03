"""Escalation helper tests — Phase 2.1."""

from __future__ import annotations

from app.db.models.chat_session import ChatSession
from app.services.escalation_service import format_escalation_note, should_auto_escalate


def test_should_auto_escalate_on_keywords() -> None:
    assert should_auto_escalate("I need a human agent please", agent_error=None) is True
    assert should_auto_escalate("hello", agent_error=None) is False


def test_should_auto_escalate_on_agent_error() -> None:
    assert should_auto_escalate("hello", agent_error="Max tool rounds") is True


def test_format_escalation_note_includes_transcript() -> None:
    session = ChatSession(
        external_id="sess-1",
        jwt_subject="staff-1",
        source="android",
        branch_id="branch-1",
        status="active",
        messages_json=[
            {"role": "user", "content": "Printer offline", "at": "2026-06-02T12:00:00Z", "tool_calls": []},
            {
                "role": "assistant",
                "content": "Checking printer…",
                "at": "2026-06-02T12:00:05Z",
                "tool_calls": [
                    {
                        "tool_name": "check_printer",
                        "arguments": {"branch_id": "branch-1"},
                        "result": '{"status":"offline"}',
                        "success": True,
                    },
                ],
            },
        ],
        meta={},
    )
    note = format_escalation_note(session, reason="customer_requested_human")
    assert "Printer offline" in note
    assert "check_printer" in note
    assert "source: android" in note.lower() or "Source: android" in note
