#!/usr/bin/env python3
"""Register (or list) Chatwoot account webhooks for ButterPOS middleware.

Chatwoot must be able to reach the callback URL. When Chatwoot runs in Docker on
Linux, use --docker-host so the URL uses host.docker.internal instead of 127.0.0.1.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import Settings, get_settings
from app.providers.ticketing.chatwoot.auth import missing_config_fields
from app.providers.ticketing.chatwoot_adapter import ChatwootAdapter

WEBHOOK_PATH = "/api/v1/webhooks/chatwoot"


def resolve_callback_url(settings: Settings, *, docker_host: bool, callback_url: str | None) -> str:
    if callback_url:
        return callback_url.rstrip("/") if callback_url.endswith("/") else callback_url

    override = settings.chatwoot_webhook_callback_url.strip()
    if override:
        return override.rstrip("/")

    if docker_host:
        port = settings.middleware_port
        return f"http://host.docker.internal:{port}{WEBHOOK_PATH}"

    base = settings.middleware_base_url.rstrip("/")
    return f"{base}{WEBHOOK_PATH}"


def _extract_webhook_rows(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in data:
        if "url" in item:
            rows.append(item)
            continue
        nested = item.get("webhook")
        if isinstance(nested, dict):
            rows.append(nested)
    return rows


def _extract_secret(result: dict[str, Any]) -> str | None:
    for key in ("secret",):
        if result.get(key):
            return str(result[key])
    nested = result.get("webhook")
    if isinstance(nested, dict) and nested.get("secret"):
        return str(nested["secret"])
    payload = result.get("payload")
    if isinstance(payload, dict):
        if payload.get("secret"):
            return str(payload["secret"])
        wh = payload.get("webhook")
        if isinstance(wh, dict) and wh.get("secret"):
            return str(wh["secret"])
    return None


async def run(args: argparse.Namespace) -> int:
    get_settings.cache_clear()
    settings = get_settings()

    missing = missing_config_fields(settings)
    if not settings.chatwoot_inbox_id:
        missing.append("CHATWOOT_INBOX_ID")
    if missing:
        print("Missing Chatwoot config:", ", ".join(missing), file=sys.stderr)
        return 1

    callback = resolve_callback_url(
        settings,
        docker_host=args.docker_host,
        callback_url=args.callback_url,
    )

    adapter = ChatwootAdapter(settings)
    try:
        existing = await adapter.list_webhooks()
        rows = _extract_webhook_rows(existing)

        if args.list or args.dry_run:
            print("=== Chatwoot webhooks ===\n")
            if not rows:
                print("  (none registered)")
            for row in rows:
                print(f"  id={row.get('id')} url={row.get('url')}")
                subs = row.get("subscriptions")
                if subs:
                    print(f"    subscriptions={subs}")
            print()

        if args.dry_run:
            print("Would register callback URL:")
            print(f"  {callback}")
            print("\nSubscriptions:", ", ".join(settings.chatwoot_webhook_subscription_list()))
            _print_next_steps(settings, secret=None, callback=callback)
            return 0

        if not args.force:
            for row in rows:
                if str(row.get("url", "")).rstrip("/") == callback.rstrip("/"):
                    print(f"Webhook already registered for {callback}")
                    print("Use --force to register a duplicate, or --list to inspect.")
                    _print_next_steps(settings, secret=None, callback=callback)
                    return 0

        if args.list and not args.register:
            return 0

        print(f"Registering webhook → {callback}")
        result = await adapter.register_webhook(callback)
        secret = _extract_secret(result)

        if args.json:
            print(json.dumps({"callback_url": callback, "result": result, "secret_present": bool(secret)}, indent=2))
        else:
            print("\n=== Registration OK ===\n")
            print(f"  Callback: {callback}")
            if secret:
                print(f"  Secret:   (returned — add to .env as CHATWOOT_WEBHOOK_SECRET)")
            else:
                print("  Secret:   not in API response — copy from Chatwoot UI if this is a re-register")
            _print_next_steps(settings, secret=secret, callback=callback)

        return 0
    finally:
        await adapter._client.close()


def _print_next_steps(settings: Settings, *, secret: str | None, callback: str) -> None:
    host = urlparse(callback).hostname or ""
    print("\n--- Next steps ---")
    if secret:
        print("1. Add to .env (do not commit):")
        print(f"   CHATWOOT_WEBHOOK_CALLBACK_URL={callback}")
        print(f"   CHATWOOT_WEBHOOK_SECRET={secret}")
    elif not settings.chatwoot_webhook_secret.strip():
        print("1. Set CHATWOOT_WEBHOOK_SECRET in .env (from Chatwoot webhook settings)")
        print(f"   CHATWOOT_WEBHOOK_CALLBACK_URL={callback}")
    print("2. Restart middleware: uvicorn app.main:app --reload --port 8000")
    print("3. Start Celery worker: celery -A app.worker.celery_app worker -l info")
    if host in {"127.0.0.1", "localhost"}:
        print(
            "4. If Chatwoot runs in Docker, re-run with --docker-host "
            "(127.0.0.1 is not reachable from inside a container)"
        )
    print("5. Human reply in Chatwoot → Celery log should show human_reply_relayed")
    print("   (Poll fallback: GET /api/v1/chat/sessions/{id} also pulls from Chatwoot)")


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Register Chatwoot webhook for ButterPOS middleware")
    parser.add_argument(
        "--callback-url",
        default="",
        help=f"Full webhook URL (default: MIDDLEWARE_BASE_URL + {WEBHOOK_PATH})",
    )
    parser.add_argument(
        "--docker-host",
        action="store_true",
        help=f"Use http://host.docker.internal:PORT{WEBHOOK_PATH} (Chatwoot in Docker, middleware on host)",
    )
    parser.add_argument("--list", action="store_true", help="List existing account webhooks")
    parser.add_argument("--register", action="store_true", help="With --list, also register if missing")
    parser.add_argument("--dry-run", action="store_true", help="Print URL and subscriptions only")
    parser.add_argument("--force", action="store_true", help="Register even if the same URL exists")
    parser.add_argument("--json", action="store_true", help="Machine-readable output on register")
    args = parser.parse_args()

    if args.callback_url and args.docker_host:
        print("Use either --callback-url or --docker-host, not both", file=sys.stderr)
        return 1

    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
