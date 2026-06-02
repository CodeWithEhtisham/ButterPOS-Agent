"""Global FastAPI exception handlers."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.config import Settings
from app.core.context import get_log_context
from app.core.exceptions import AppError
from app.core.logging_config import get_logger

logger = get_logger("app.errors")


def _error_body(detail: str) -> dict[str, str]:
    return {"detail": detail}


def register_exception_handlers(app: FastAPI, settings: Settings) -> None:
    """Attach handlers for HTTP, application, and unhandled errors."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        ctx = get_log_context()
        logger.warning(
            "http_exception status=%s detail=%s path=%s",
            exc.status_code,
            exc.detail,
            request.url.path,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": exc.status_code,
                **{k: v for k, v in ctx.items() if v is not None},
            },
        )
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        ctx = get_log_context()
        log_fn = logger.warning if exc.status_code < 500 else logger.error
        log_fn(
            "app_error status=%s message=%s path=%s",
            exc.status_code,
            exc.message,
            request.url.path,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": exc.status_code,
                **{k: v for k, v in ctx.items() if v is not None},
            },
        )
        return JSONResponse(status_code=exc.status_code, content=_error_body(exc.message))

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        ctx = get_log_context()
        logger.exception(
            "unhandled_exception path=%s",
            request.url.path,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": 500,
                **{k: v for k, v in ctx.items() if v is not None},
            },
        )
        detail = str(exc) if settings.debug else "Internal server error"
        return JSONResponse(status_code=500, content=_error_body(detail))
