#!/usr/bin/env python3
"""Smoke test — prove middleware runs against live infra (Phase 1 exit 1.8.1)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _check(name: str, ok: bool, detail: str) -> bool:
    print(f"  [{'OK' if ok else 'FAIL'}] {name}: {detail}")
    return ok


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Middleware smoke test")
    parser.add_argument(
        "--base-url",
        default=os.getenv("MIDDLEWARE_BASE_URL", "http://127.0.0.1:8000"),
        help="Running middleware base URL",
    )
    parser.add_argument(
        "--skip-infra",
        action="store_true",
        help="Skip scripts/check_infra.py (Postgres + Redis direct probe)",
    )
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    ok = True

    print("=== Middleware smoke test (Task 1.8.1) ===\n")

    if not args.skip_infra:
        from scripts.check_infra import check_postgres, check_redis

        pg_ok, pg_msg = check_postgres()
        ok &= _check("infra_postgres", pg_ok, pg_msg)
        redis_ok, redis_msg = check_redis()
        ok &= _check("infra_redis", redis_ok, redis_msg)
        print()

    client_id = os.getenv("API_CLIENT_ID", "")
    client_secret = os.getenv("API_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        ok &= _check("env_auth", False, "API_CLIENT_ID / API_CLIENT_SECRET not set")
        print("\nRESULT: FAIL")
        return 1

    try:
        with httpx.Client(base_url=base, timeout=10.0) as client:
            openapi = client.get("/openapi.json")
            ok &= _check(
                "openapi",
                openapi.status_code == 200,
                f"HTTP {openapi.status_code}",
            )

            health = client.get("/api/v1/system/health")
            health_ok = health.status_code == 200
            detail = f"HTTP {health.status_code}"
            if health_ok:
                body = health.json()
                detail = f"healthy={body.get('healthy')} components={len(body.get('components', []))}"
            ok &= _check("system_health", health_ok, detail)

            token_resp = client.post(
                "/api/v1/auth/token",
                json={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "subject": "smoke-test",
                },
            )
            token_ok = token_resp.status_code == 200 and "access_token" in token_resp.json()
            ok &= _check("auth_token", token_ok, f"HTTP {token_resp.status_code}")

            if token_ok:
                token = token_resp.json()["access_token"]
                me = client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {token}"},
                )
                me_ok = me.status_code == 200 and me.json().get("subject") == "smoke-test"
                ok &= _check("auth_me", me_ok, f"HTTP {me.status_code}")
    except httpx.ConnectError as exc:
        ok &= _check("http_connect", False, str(exc))
        print("\nHint: start the app with: uvicorn app.main:app --host 0.0.0.0 --port 8000")
    except Exception as exc:  # noqa: BLE001
        ok &= _check("http_request", False, str(exc))

    print()
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
