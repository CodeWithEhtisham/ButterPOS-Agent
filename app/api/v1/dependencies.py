"""Shared FastAPI dependencies for API v1."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.core.ticketing.interface import TicketingProvider
from app.core.ticketing.factory import get_ticketing_provider

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

_ticketing_provider: TicketingProvider | None = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_redis():
    """Returns a Redis client instance. Configured in startup event."""
    from app.utils.redis_client import get_redis_client
    return await get_redis_client()


def get_ticketing() -> TicketingProvider:
    global _ticketing_provider
    if _ticketing_provider is None:
        _ticketing_provider = get_ticketing_provider()
    return _ticketing_provider
