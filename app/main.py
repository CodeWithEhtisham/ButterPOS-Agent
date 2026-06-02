"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.v1.router import api_v1_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    """Build the FastAPI application (factory pattern for tests)."""
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
    )
    application.include_router(api_v1_router)
    return application


app = create_app()
