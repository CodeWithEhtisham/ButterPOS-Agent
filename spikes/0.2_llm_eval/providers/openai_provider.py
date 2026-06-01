"""OpenAI adapter — only imported inside provider layer, never by middleware core."""

from __future__ import annotations

import time
from typing import Any

from openai import AsyncOpenAI
from providers.base import LLMProvider, LLMRequest, LLMResponse

# USD per 1M tokens (input, output) — update when OpenAI pricing changes
PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
}


class OpenAIProvider(LLMProvider):
    provider_name = "openai"

    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)

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

        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            latency_ms=round(latency_ms, 2),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=round(cost, 6),
            raw={"id": response.id},
        )
