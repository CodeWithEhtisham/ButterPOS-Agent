"""Chatwoot adapter exceptions."""

from __future__ import annotations

from app.core.exceptions import AppError


class ChatwootConfigError(AppError):
    """Missing or invalid Chatwoot configuration."""

    status_code = 503

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)


class ChatwootAuthError(ChatwootConfigError):
    """API token missing or rejected by Chatwoot."""


class ChatwootAPIError(AppError):
    """Chatwoot HTTP API returned an error."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 502,
        chatwoot_status: int | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code)
        self.chatwoot_status = chatwoot_status
