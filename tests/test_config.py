"""Tests for application configuration — Task 1.1 sub-step 1."""

from __future__ import annotations

import pytest
from app.core.config import Settings, get_settings


def test_settings_defaults() -> None:
    settings = Settings()
    assert settings.app_name == "ButterPOS Support Agent"
    assert settings.ticketing_provider == "chatwoot"
    assert settings.llm_primary_model == "openai/gpt-4o"
    assert settings.openrouter_base_url == "https://openrouter.ai/api/v1"
    assert "asyncpg" in settings.database_url


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "Test Agent")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("TICKETING_PROVIDER", "chatwoot")
    monkeypatch.setenv("LLM_PRIMARY_MODEL", "anthropic/claude-3-haiku")
    settings = Settings()
    assert settings.app_name == "Test Agent"
    assert settings.log_level == "DEBUG"
    assert settings.llm_primary_model == "anthropic/claude-3-haiku"


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("APP_NAME", "Cached Name")
    first = get_settings()
    second = get_settings()
    assert first is second
    get_settings.cache_clear()


def test_empty_chatwoot_ids_coerced_to_zero() -> None:
    settings = Settings(_env_file=None, chatwoot_account_id="", chatwoot_inbox_id="")
    assert settings.chatwoot_account_id == 0
    assert settings.chatwoot_inbox_id == 0
