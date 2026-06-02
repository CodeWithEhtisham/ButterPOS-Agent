"""LLM provider interface — D-3; no vendor SDKs in core services."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMRequest:
    messages: list[dict[str, Any]]
    model: str
    temperature: float = 0.2
    max_tokens: int = 1024
    tools: list[dict[str, Any]] | None = None


@dataclass
class LLMResponse:
    content: str
    model: str
    latency_ms: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    provider_name: str

    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Run a chat completion and return normalized response."""

    @abstractmethod
    def estimate_cost_usd(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        """Estimate cost in USD for token usage."""
