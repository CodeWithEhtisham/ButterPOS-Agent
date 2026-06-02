"""FastAPI application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.middleware.request_logging import RequestLoggingMiddleware
from app.api.v1.router import api_v1_router
from app.core.config import Settings, get_settings
from app.core.error_handlers import register_exception_handlers
from app.core.logging_config import configure_logging


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging(get_settings())
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application (factory pattern for tests)."""
    app_settings = settings or get_settings()
    application = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        debug=app_settings.debug,
        lifespan=lifespan,
    )
    application.add_middleware(RequestLoggingMiddleware)
    register_exception_handlers(application, app_settings)
    application.include_router(api_v1_router)
    return application


app = create_app()
