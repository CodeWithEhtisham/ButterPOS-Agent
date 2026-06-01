"""OpenRouter adapter — unified gateway for OpenAI, Anthropic, Gemini, etc.

Uses the OpenAI-compatible HTTP API; only imported inside the provider layer (D-3).
"""

from __future__ import annotations

import os
import time
from typing import Any

from openai import AsyncOpenAI
from providers.base import LLMProvider, LLMRequest, LLMResponse

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# USD per 1M tokens (input, output) — approximate; update from openrouter.ai/models
PRICING: dict[str, tuple[float, float]] = {
    "openai/gpt-4o": (2.50, 10.00),
    "openai/gpt-4o-mini": (0.15, 0.60),
    "anthropic/claude-3.5-sonnet": (3.00, 15.00),
    "anthropic/claude-3-haiku": (0.25, 1.25),
    "google/gemini-2.0-flash-001": (0.10, 0.40),
}


class OpenRouterProvider(LLMProvider):
    provider_name = "openrouter"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        app_url: str | None = None,
        app_name: str | None = None,
    ) -> None:
        default_headers: dict[str, str] = {}
        referer = app_url or os.getenv("OPENROUTER_APP_URL", "")
        title = app_name or os.getenv("OPENROUTER_APP_NAME", "ButterPOS Support Agent")
        if referer:
            default_headers["HTTP-Referer"] = referer
        if title:
            default_headers["X-Title"] = title

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url or os.getenv("OPENROUTER_BASE_URL", OPENROUTER_BASE_URL),
            default_headers=default_headers or None,
        )

    def estimate_cost_usd(
        self, model: str, prompt_tokens: int, completion_tokens: int
    ) -> float:
        input_rate, output_rate = PRICING.get(model, (0.0, 0.0))
        return (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000

    async def complete(self, request: LLMRequest) -> LLMResponse:
        start = time.perf_counter()
        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.tools:
            kwargs["tools"] = request.tools

        response = await self._client.chat.completions.create(**kwargs)
        latency_ms = (time.perf_counter() - start) * 1000

        choice = response.choices[0]
        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else prompt_tokens + completion_tokens

        cost = self.estimate_cost_usd(request.model, prompt_tokens, completion_tokens)

        tool_calls: list[dict[str, Any]] | None = None
        if choice.message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in choice.message.tool_calls
            ]

        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            latency_ms=round(latency_ms, 2),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=round(cost, 6),
            raw={
                "id": response.id,
                "tool_calls": tool_calls,
                "finish_reason": choice.finish_reason,
            },
        )
