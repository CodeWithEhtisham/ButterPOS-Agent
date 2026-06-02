"""Async Chatwoot Application API client — auth, timeout, retry (Task 1.3.1)."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from app.core.config import Settings
from app.providers.ticketing.chatwoot.auth import missing_config_fields, resolve_api_token
from app.providers.ticketing.chatwoot.errors import ChatwootAPIError, ChatwootAuthError, ChatwootConfigError

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


class ChatwootClient:
    """Thin async wrapper around Chatwoot's Application API."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    @property
    def account_id(self) -> int:
        return self._settings.chatwoot_account_id

    @property
    def inbox_id(self) -> int:
        return self._settings.chatwoot_inbox_id

    def ensure_configured(self) -> None:
        """Fail fast when required Chatwoot env vars are absent."""
        missing = missing_config_fields(self._settings)
        if missing:
            raise ChatwootConfigError(f"Missing configuration: {', '.join(missing)}")

    def _headers(self) -> dict[str, str]:
        return {
            "api_access_token": resolve_api_token(self._settings),
            "Content-Type": "application/json",
        }

    def _http_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._settings.chatwoot_base_url.rstrip("/"),
                headers=self._headers(),
                timeout=self._settings.chatwoot_request_timeout_seconds,
                transport=self._transport,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """HTTP request with bounded retries on transient failures."""
        self.ensure_configured()
        client = self._http_client()
        max_attempts = self._settings.chatwoot_max_retries
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                response = await client.request(method, path, json=json, params=params)
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning(
                    "Chatwoot request timeout",
                    extra={"method": method, "path": path, "attempt": attempt},
                )
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning(
                    "Chatwoot transport error",
                    extra={"method": method, "path": path, "attempt": attempt, "error": str(exc)},
                )
            else:
                if response.status_code == 401:
                    raise ChatwootAuthError("Chatwoot rejected api_access_token (HTTP 401)")
                if response.status_code in _RETRYABLE_STATUS and attempt < max_attempts:
                    logger.warning(
                        "Chatwoot retryable status",
                        extra={
                            "method": method,
                            "path": path,
                            "status": response.status_code,
                            "attempt": attempt,
                        },
                    )
                    await asyncio.sleep(min(0.5 * attempt, 2.0))
                    continue
                if response.is_error:
                    raise ChatwootAPIError(
                        f"Chatwoot API error {response.status_code} for {method} {path}",
                        chatwoot_status=response.status_code,
                    )
                return response

            if attempt < max_attempts:
                await asyncio.sleep(min(0.5 * attempt, 2.0))

        raise ChatwootAPIError(
            f"Chatwoot request failed after {max_attempts} attempts: {method} {path}",
            status_code=503,
        ) from last_error

    async def ping(self) -> float:
        """Probe Chatwoot reachability; returns round-trip latency in milliseconds."""
        start = time.perf_counter()
        await self.request("GET", "/api")
        return (time.perf_counter() - start) * 1000.0

    def account_path(self, suffix: str = "") -> str:
        """Build `/api/v1/accounts/{id}{suffix}` path."""
        base = f"/api/v1/accounts/{self.account_id}"
        return f"{base}{suffix}" if suffix else base
