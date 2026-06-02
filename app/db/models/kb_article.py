"""Knowledge base article ORM model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.kb_article_version import KBArticleVersion


class KBArticle(Base, TimestampMixin):
    """Live KB article — bilingual content with pointer to latest version number."""

    __tablename__ = "kb_articles"

    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", server_default="draft")
    content_en: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_ur: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    author: Mapped[str | None] = mapped_column(String(128), nullable=True)
    roman_urdu_needed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    tags: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    versions: Mapped[list[KBArticleVersion]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        order_by="KBArticleVersion.version_number",
    )
