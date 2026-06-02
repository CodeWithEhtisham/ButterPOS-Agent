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
from app.core.mcp.factory import clear_mcp_client_cache, init_mcp_client, shutdown_mcp_client
from app.db.session import init_engine, shutdown_engine


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings)
    init_engine(settings)
    try:
        await init_mcp_client(settings)
    except Exception:
        clear_mcp_client_cache()
    yield
    await shutdown_mcp_client()
    clear_mcp_client_cache()
    await shutdown_engine()


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
