"""KB article version history ORM model — immutable snapshots for rollback."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.kb_article import KBArticle


class KBArticleVersion(Base, TimestampMixin):
    """Immutable edit snapshot — rollback creates a new version from a prior row."""

    __tablename__ = "kb_article_versions"
    __table_args__ = (UniqueConstraint("article_id", "version_number", name="uq_kb_article_version"),)

    article_id: Mapped[int] = mapped_column(
        ForeignKey("kb_articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_en: Mapped[str] = mapped_column(Text, nullable=False)
    content_ur: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_summary: Mapped[str | None] = mapped_column(String(512), nullable=True)
    edited_by: Mapped[str | None] = mapped_column(String(128), nullable=True)

    article: Mapped[KBArticle] = relationship(back_populates="versions")
