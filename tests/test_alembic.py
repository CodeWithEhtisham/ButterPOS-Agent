"""Alembic migration tests — Task 1.2 sub-step 6."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.db.base import Base
from app.db.models import (  # noqa: F401 — register metadata
    AIConversation,
    Branch,
    KBArticle,
    KBArticleVersion,
    Restaurant,
    SLAConfig,
    TicketCache,
    User,
    WebhookEventLog,
)
from app.db.url import to_sync_database_url

EXPECTED_TABLES = {
    "restaurants",
    "branches",
    "users",
    "ticket_cache",
    "ai_conversations",
    "kb_articles",
    "kb_article_versions",
    "webhook_event_log",
    "sla_config",
}


def test_to_sync_database_url_asyncpg() -> None:
    url = "postgresql+asyncpg://butterpos:butterpos@localhost:5432/butterpos"
    assert to_sync_database_url(url) == "postgresql+psycopg2://butterpos:butterpos@localhost:5432/butterpos"


def test_to_sync_database_url_plain_postgresql() -> None:
    url = "postgresql://butterpos:butterpos@localhost:5432/butterpos"
    assert to_sync_database_url(url) == "postgresql+psycopg2://butterpos:butterpos@localhost:5432/butterpos"


def test_alembic_has_single_head_revision() -> None:
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert heads == ["20260602_0001"]


def test_initial_migration_mentions_all_tables() -> None:
    root = Path(__file__).resolve().parents[1]
    migration = (root / "alembic" / "versions" / "20260602_0001_initial_schema.py").read_text()
    for table in EXPECTED_TABLES:
        assert f'"{table}"' in migration


def test_orm_metadata_matches_expected_tables() -> None:
    names = {t.name for t in Base.metadata.sorted_tables}
    assert EXPECTED_TABLES.issubset(names)
