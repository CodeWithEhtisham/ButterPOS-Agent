"""Database URL helpers — async runtime vs sync Alembic migrations."""

from __future__ import annotations


def to_sync_database_url(url: str) -> str:
    """Convert async SQLAlchemy URL to psycopg2 for Alembic offline/online migrations."""
    if "+asyncpg" in url:
        return url.replace("+asyncpg", "+psycopg2", 1)
    if url.startswith("postgresql://") and "+psycopg" not in url:
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url
