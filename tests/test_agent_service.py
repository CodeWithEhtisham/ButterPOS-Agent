"""Agent service prompt and behavior tests."""

from app.services.agent_service import SYSTEM_PROMPT


def test_system_prompt_includes_bilingual_language_rules() -> None:
    """D-5: agent must mirror English, Roman Urdu, and code-switched user messages."""
    assert "Roman Urdu" in SYSTEM_PROMPT
    assert "Match the user's language" in SYSTEM_PROMPT
    assert "Code-switched" in SYSTEM_PROMPT
    assert "Do not switch to English only" in SYSTEM_PROMPT
