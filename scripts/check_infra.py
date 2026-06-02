#!/usr/bin/env python3
"""Verify Postgres and Redis are reachable (Step 0.5 infra check)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings


def check_postgres() -> tuple[bool, str]:
    settings = get_settings()
    url = settings.database_url
    if not url:
        return False, "DATABASE_URL not set"
    sync_url = url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgres+asyncpg://", "postgresql://"
    )
    try:
        import psycopg2

        conn = psycopg2.connect(sync_url)
        cur = conn.cursor()
        cur.execute("SELECT version()")
        version = cur.fetchone()[0]
        conn.close()
        return True, version[:60]
    except ImportError:
        return False, "psycopg2 not installed (pip install psycopg2-binary)"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def check_redis() -> tuple[bool, str]:
    settings = get_settings()
    url = settings.redis_url
    try:
        import redis

        client = redis.from_url(url)
        pong = client.ping()
        info = client.info("server")
        return bool(pong), f"Redis {info.get('redis_version', 'unknown')}"
    except ImportError:
        return False, "redis not installed (pip install redis)"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def main() -> int:
    get_settings.cache_clear()
    print("=== Infrastructure check (Postgres + Redis) ===\n")
    ok = True

    pg_ok, pg_msg = check_postgres()
    print(f"  Postgres: {'OK' if pg_ok else 'FAIL'} — {pg_msg}")
    ok &= pg_ok

    redis_ok, redis_msg = check_redis()
    print(f"  Redis:    {'OK' if redis_ok else 'FAIL'} — {redis_msg}")
    ok &= redis_ok

    print()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
