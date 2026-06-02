"""LLM provider factory."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.providers.llm.base import LLMProvider
from app.providers.llm.openrouter import OpenRouterProvider


@lru_cache
def get_llm_provider() -> LLMProvider:
    return OpenRouterProvider(get_settings())


def clear_llm_provider_cache() -> None:
    get_llm_provider.cache_clear()
