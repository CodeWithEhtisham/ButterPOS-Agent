"""Middleware readiness probes — Postgres + Redis (Task 1.8.1)."""

from __future__ import annotations

import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.schemas.system import ComponentHealth, SystemHealthResponse


async def _check_postgres(session: AsyncSession) -> ComponentHealth:
    try:
        result = await session.execute(text("SELECT 1"))
        ok = result.scalar_one() == 1
        return ComponentHealth(name="postgres", healthy=ok, message=None if ok else "unexpected result")
    except Exception as exc:  # noqa: BLE001
        return ComponentHealth(name="postgres", healthy=False, message=str(exc))


async def _check_redis(redis_url: str) -> ComponentHealth:
    client = aioredis.from_url(redis_url, decode_responses=True)
    try:
        pong = await client.ping()
        return ComponentHealth(
            name="redis",
            healthy=bool(pong),
            message=None if pong else "ping failed",
        )
    except Exception as exc:  # noqa: BLE001
        return ComponentHealth(name="redis", healthy=False, message=str(exc))
    finally:
        await client.aclose()


async def collect_system_health(
    settings: Settings,
    session: AsyncSession,
) -> SystemHealthResponse:
    """Probe Postgres and Redis; aggregate overall readiness."""
    components = [
        await _check_postgres(session),
        await _check_redis(settings.redis_url),
    ]
    healthy = all(component.healthy for component in components)
    return SystemHealthResponse(
        healthy=healthy,
        app=settings.app_name,
        version=settings.app_version,
        components=components,
    )
