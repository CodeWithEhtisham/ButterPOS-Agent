"""Async SQLAlchemy engine and session factory."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(settings: Settings | None = None) -> AsyncEngine:
    """Create (or return cached) async engine from DATABASE_URL."""
    global _engine, _session_factory
    app_settings = settings or get_settings()
    if _engine is None:
        _engine = create_async_engine(
            app_settings.database_url,
            echo=app_settings.debug,
            pool_pre_ping=True,
        )
        _session_factory = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _engine


async def shutdown_engine() -> None:
    """Dispose engine on application shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    init_engine()
    if _session_factory is None:
        raise RuntimeError("Session factory not initialized")
    return _session_factory


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a session with commit/rollback."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def clear_session_cache() -> None:
    """Reset cached factory — for tests."""
    get_session_factory.cache_clear()
