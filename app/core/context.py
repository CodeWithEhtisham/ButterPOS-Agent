"""Request-scoped context for structured logging."""

from __future__ import annotations

from contextvars import ContextVar, Token

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
ticket_id_var: ContextVar[str | None] = ContextVar("ticket_id", default=None)


def set_request_id(value: str) -> Token[str | None]:
    return request_id_var.set(value)


def set_user_id(value: str | None) -> Token[str | None]:
    return user_id_var.set(value)


def set_ticket_id(value: str | None) -> Token[str | None]:
    return ticket_id_var.set(value)


def reset_context(token: Token[str | None]) -> None:
    request_id_var.reset(token)


def reset_user_id(token: Token[str | None]) -> None:
    user_id_var.reset(token)


def reset_ticket_id(token: Token[str | None]) -> None:
    ticket_id_var.reset(token)


def get_log_context() -> dict[str, str | None]:
    return {
        "request_id": request_id_var.get(),
        "user_id": user_id_var.get(),
        "ticket_id": ticket_id_var.get(),
    }
