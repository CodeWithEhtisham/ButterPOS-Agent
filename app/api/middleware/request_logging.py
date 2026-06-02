"""Request logging middleware with correlation ids and optional JWT subject."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import Settings, get_settings
from app.core.context import (
    reset_context,
    reset_ticket_id,
    reset_user_id,
    set_request_id,
    set_ticket_id,
    set_user_id,
)
from app.core.logging_config import get_logger
from app.core.security import InvalidTokenError, decode_access_token

logger = get_logger("app.request")


def _optional_user_id(request: Request, settings: Settings) -> str | None:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    if not token or not settings.jwt_secret:
        return None
    try:
        payload = decode_access_token(token, settings)
    except InvalidTokenError:
        return None
    return payload.sub


def _optional_ticket_id(request: Request) -> str | None:
    ticket = request.path_params.get("provider_ticket_id") or request.path_params.get("ticket_id")
    if ticket:
        return str(ticket)
    query_ticket = request.query_params.get("ticket_id")
    return str(query_ticket) if query_ticket else None


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request with timestamp, user_id, ticket_id when available."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()
        request_id = str(uuid.uuid4())
        req_token = set_request_id(request_id)

        user_id = _optional_user_id(request, settings)
        user_token = set_user_id(user_id) if user_id else None

        ticket_id = _optional_ticket_id(request)
        ticket_token = set_ticket_id(ticket_id) if ticket_id else None

        start = time.perf_counter()
        client_ip = request.client.host if request.client else None

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.exception(
                "request_failed method=%s path=%s duration_ms=%s",
                request.method,
                request.url.path,
                duration_ms,
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "duration_ms": duration_ms,
                    "client_ip": client_ip,
                },
            )
            raise
        else:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "request_completed method=%s path=%s status=%s duration_ms=%s "
                "user_id=%s ticket_id=%s",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                user_id,
                ticket_id,
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "client_ip": client_ip,
                },
            )
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            reset_context(req_token)
            if user_token is not None:
                reset_user_id(user_token)
            if ticket_token is not None:
                reset_ticket_id(ticket_token)
