"""Database session factory tests — Task 1.2 sub-step 1."""

from __future__ import annotations

import asyncio

import pytest
from app.core.config import Settings
from app.db.session import clear_session_cache, init_engine, shutdown_engine


@pytest.fixture(autouse=True)
def reset_engine() -> None:
    asyncio.run(shutdown_engine())
    clear_session_cache()
    yield
    asyncio.run(shutdown_engine())
    clear_session_cache()


def test_init_engine_from_settings() -> None:
    async def _run() -> None:
        settings = Settings(
            _env_file=None,
            database_url="postgresql+asyncpg://butterpos:butterpos@localhost:5432/butterpos",
        )
        engine = init_engine(settings)
        assert str(engine.url).startswith("postgresql+asyncpg://")
        await shutdown_engine()

    asyncio.run(_run())
