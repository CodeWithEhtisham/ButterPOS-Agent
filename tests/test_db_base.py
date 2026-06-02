"""SQLAlchemy base model tests — Task 1.2 sub-step 1."""

from __future__ import annotations

from app.db.base import Base, TimestampMixin
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class _SampleRecord(Base, TimestampMixin):
    """Minimal concrete model for mixin verification (not migrated)."""

    __tablename__ = "sample_records"
    name: Mapped[str] = mapped_column(String(64), nullable=False)


def test_timestamp_mixin_columns() -> None:
    columns = _SampleRecord.__table__.columns
    assert "id" in columns
    assert "created_at" in columns
    assert "updated_at" in columns
    assert columns["id"].primary_key
    assert columns["created_at"].nullable is False
    assert columns["updated_at"].nullable is False


def test_base_registers_table_in_metadata() -> None:
    assert "sample_records" in Base.metadata.tables
    table = Base.metadata.tables["sample_records"]
    assert "name" in table.columns
