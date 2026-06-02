"""KB article + version history ORM tests — Task 1.2 sub-step 4."""

from __future__ import annotations

from app.db.base import Base
from app.db.models import KBArticle, KBArticleVersion
from sqlalchemy.dialects.postgresql import JSONB


def test_kb_article_table_columns() -> None:
    columns = KBArticle.__table__.columns
    assert columns["slug"].unique
    assert columns["category"].nullable is False
    assert columns["content_en"].nullable is False
    assert columns["content_ur"].nullable is True
    assert columns["current_version"].nullable is False
    assert columns["roman_urdu_needed"].nullable is False
    assert isinstance(columns["tags"].type, JSONB)


def test_kb_article_version_table_columns() -> None:
    columns = KBArticleVersion.__table__.columns
    assert columns["article_id"].foreign_keys
    assert columns["version_number"].nullable is False
    assert columns["content_en"].nullable is False
    assert columns["content_ur"].nullable is True
    assert columns["change_summary"].nullable is True


def test_kb_article_version_unique_constraint() -> None:
    constraints = {c.name for c in KBArticleVersion.__table__.constraints if hasattr(c, "name")}
    assert "uq_kb_article_version" in constraints


def test_kb_article_relationships() -> None:
    assert KBArticle.versions.property.mapper.class_ is KBArticleVersion
    assert KBArticleVersion.article.property.mapper.class_ is KBArticle


def test_kb_models_in_metadata() -> None:
    names = {t.name for t in Base.metadata.sorted_tables}
    assert {"kb_articles", "kb_article_versions"}.issubset(names)
