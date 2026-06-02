"""Structured logging configuration."""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from typing import Any

import orjson

from app.core.config import Settings
from app.core.context import get_log_context


class ContextFilter(logging.Filter):
    """Inject request context vars into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = get_log_context()
        record.request_id = ctx["request_id"]
        record.user_id = ctx["user_id"]
        record.ticket_id = ctx["ticket_id"]
        return True


class JsonLogFormatter(logging.Formatter):
    """One JSON object per log line for ingestion by log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "user_id": getattr(record, "user_id", None),
            "ticket_id": getattr(record, "ticket_id", None),
        }
        for key in ("method", "path", "status_code", "duration_ms", "client_ip"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return orjson.dumps(payload).decode()


def configure_logging(settings: Settings) -> None:
    """Configure root logger once at application startup."""
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(settings.log_level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    handler.addFilter(ContextFilter())
    root.addHandler(handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
