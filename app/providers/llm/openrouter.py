"""OpenRouter LLM adapter — D-11."""

from __future__ import annotations

import time
from typing import Any

from openai import AsyncOpenAI

from app.core.config import Settings
from app.providers.llm.base import LLMProvider, LLMRequest, LLMResponse


class OpenRouterProvider(LLMProvider):
    provider_name = "openrouter"

    def __init__(self, settings: Settings) -> None:
        headers: dict[str, str] = {}
        if settings.openrouter_app_url:
            headers["HTTP-Referer"] = settings.openrouter_app_url
        if settings.openrouter_app_name:
            headers["X-Title"] = settings.openrouter_app_name
        self._client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            default_headers=headers or None,
        )

    def estimate_cost_usd(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        del model, prompt_tokens, completion_tokens
        return 0.0

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

        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0

        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            latency_ms=round(latency_ms, 2),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=usage.total_tokens if usage else prompt_tokens + completion_tokens,
            raw={"tool_calls": tool_calls, "finish_reason": choice.finish_reason},
        )
