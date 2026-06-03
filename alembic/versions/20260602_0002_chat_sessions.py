"""Add chat_sessions table — Phase 2.1 conversation persistence.

Revision ID: 20260602_0002
Revises: 20260602_0001
Create Date: 2026-06-02
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260602_0002"
down_revision: Union[str, None] = "20260602_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("jwt_subject", sa.String(length=128), nullable=False),
        sa.Column("source", sa.String(length=16), server_default="test", nullable=False),
        sa.Column("branch_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("provider_ticket_id", sa.String(length=128), nullable=True),
        sa.Column("provider_contact_id", sa.String(length=128), nullable=True),
        sa.Column("messages_json", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index("ix_chat_sessions_external_id", "chat_sessions", ["external_id"])
    op.create_index("ix_chat_sessions_jwt_subject", "chat_sessions", ["jwt_subject"])
    op.create_index("ix_chat_sessions_provider_ticket_id", "chat_sessions", ["provider_ticket_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_sessions_provider_ticket_id", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_jwt_subject", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_external_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")
