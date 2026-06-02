#!/usr/bin/env python3
"""Seed middleware Postgres from ButterPOS tenant export — Task 1.7."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from app.core.config import get_settings
from app.db.session import get_session_factory, init_engine
from app.services.tenant_export_loader import TenantExportLoadError, load_tenant_export
from app.services.tenant_seed_service import TenantSeedService


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and load ButterPOS restaurant/branch/user export into Postgres.",
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        required=True,
        help="Path to export.json or directory with restaurants.csv, branches.csv, users.csv",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate only — do not write to Postgres",
    )
    parser.add_argument(
        "--seed-default-sla",
        action="store_true",
        help="Upsert default sla_config rows for 8h/16h/24-7 when missing from export",
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    load_dotenv()
    settings = get_settings()

    try:
        loaded = load_tenant_export(args.input)
    except TenantExportLoadError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    document = loaded.document
    print(
        f"Loaded {loaded.format} export from {loaded.source}: "
        f"{len(document.restaurants)} restaurants, "
        f"{len(document.branches)} branches, "
        f"{len(document.users)} users, "
        f"{len(document.sla_configs)} sla_configs"
    )

    init_engine(settings)
    factory = get_session_factory()
    async with factory() as session:
        service = TenantSeedService(session)
        summary = await service.seed(
            document,
            dry_run=args.dry_run,
            seed_default_sla=args.seed_default_sla,
        )
        if not summary.dry_run:
            await session.commit()

    mode = "validated (dry-run)" if summary.dry_run else "seeded"
    print(
        f"OK — {mode} {summary.restaurants} restaurants, "
        f"{summary.branches} branches, {summary.users} users, "
        f"{summary.sla_configs} sla_configs"
    )
    return 0


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
