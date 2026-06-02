"""Application-specific exceptions."""

from __future__ import annotations


class AppError(Exception):
    """Base error with HTTP status for API responses."""

    status_code: int = 500

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code


class WebhookVerificationError(AppError):
    """Inbound webhook failed HMAC or timestamp validation."""

    def __init__(self, message: str = "Invalid webhook signature") -> None:
        super().__init__(message, status_code=401)
