"""Initial middleware schema — Task 1.2 ORM tables.

Revision ID: 20260602_0001
Revises:
Create Date: 2026-06-02

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260602_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "restaurants",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("butterpos_restaurant_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("plan_type", sa.String(length=32), nullable=False),
        sa.Column("payment_due", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("butterpos_restaurant_id"),
    )
    op.create_table(
        "kb_articles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="draft", nullable=False),
        sa.Column("content_en", sa.Text(), server_default="", nullable=False),
        sa.Column("content_ur", sa.Text(), nullable=True),
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("author", sa.String(length=128), nullable=True),
        sa.Column("roman_urdu_needed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_kb_articles_category"), "kb_articles", ["category"], unique=False)
    op.create_index(op.f("ix_kb_articles_slug"), "kb_articles", ["slug"], unique=False)
    op.create_table(
        "sla_config",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("plan_type", sa.String(length=32), nullable=False),
        sa.Column("coverage_hours", sa.Integer(), nullable=False),
        sa.Column("first_response_minutes", sa.Integer(), nullable=False),
        sa.Column("resolution_minutes", sa.Integer(), nullable=False),
        sa.Column("escalation_after_minutes", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("rules", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_type"),
    )
    op.create_index(op.f("ix_sla_config_plan_type"), "sla_config", ["plan_type"], unique=False)
    op.create_table(
        "webhook_event_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("provider_event_id", sa.String(length=128), nullable=False),
        sa.Column("provider_ticket_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="received", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(op.f("ix_webhook_event_log_event_type"), "webhook_event_log", ["event_type"], unique=False)
    op.create_index(
        op.f("ix_webhook_event_log_idempotency_key"),
        "webhook_event_log",
        ["idempotency_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_webhook_event_log_provider_ticket_id"),
        "webhook_event_log",
        ["provider_ticket_id"],
        unique=False,
    )
    op.create_table(
        "branches",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("restaurant_id", sa.BigInteger(), nullable=False),
        sa.Column("butterpos_branch_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("devices", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("butterpos_branch_id"),
    )
    op.create_index(op.f("ix_branches_restaurant_id"), "branches", ["restaurant_id"], unique=False)
    op.create_table(
        "kb_article_versions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("article_id", sa.BigInteger(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content_en", sa.Text(), nullable=False),
        sa.Column("content_ur", sa.Text(), nullable=True),
        sa.Column("change_summary", sa.String(length=512), nullable=True),
        sa.Column("edited_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["kb_articles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("article_id", "version_number", name="uq_kb_article_version"),
    )
    op.create_index(op.f("ix_kb_article_versions_article_id"), "kb_article_versions", ["article_id"], unique=False)
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("butterpos_user_id", sa.String(length=64), nullable=False),
        sa.Column("branch_id", sa.BigInteger(), nullable=True),
        sa.Column("provider_contact_id", sa.String(length=128), nullable=True),
        sa.Column("language_pref", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("butterpos_user_id"),
        sa.UniqueConstraint("provider_contact_id"),
    )
    op.create_index(op.f("ix_users_branch_id"), "users", ["branch_id"], unique=False)
    op.create_table(
        "ticket_cache",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("provider_ticket_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=True),
        sa.Column("provider_contact_id", sa.String(length=128), nullable=True),
        sa.Column("assignee_id", sa.String(length=128), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_ticket_id"),
    )
    op.create_index(op.f("ix_ticket_cache_provider_ticket_id"), "ticket_cache", ["provider_ticket_id"], unique=False)
    op.create_index(op.f("ix_ticket_cache_user_id"), "ticket_cache", ["user_id"], unique=False)
    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ticket_cache_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("messages_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column(
            "confidence_history",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ticket_cache_id"], ["ticket_cache.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_cache_id"),
    )
    op.create_index(op.f("ix_ai_conversations_ticket_cache_id"), "ai_conversations", ["ticket_cache_id"], unique=False)
    op.create_index(op.f("ix_ai_conversations_user_id"), "ai_conversations", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_conversations_user_id"), table_name="ai_conversations")
    op.drop_index(op.f("ix_ai_conversations_ticket_cache_id"), table_name="ai_conversations")
    op.drop_table("ai_conversations")
    op.drop_index(op.f("ix_ticket_cache_user_id"), table_name="ticket_cache")
    op.drop_index(op.f("ix_ticket_cache_provider_ticket_id"), table_name="ticket_cache")
    op.drop_table("ticket_cache")
    op.drop_index(op.f("ix_users_branch_id"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_kb_article_versions_article_id"), table_name="kb_article_versions")
    op.drop_table("kb_article_versions")
    op.drop_index(op.f("ix_branches_restaurant_id"), table_name="branches")
    op.drop_table("branches")
    op.drop_index(op.f("ix_webhook_event_log_provider_ticket_id"), table_name="webhook_event_log")
    op.drop_index(op.f("ix_webhook_event_log_idempotency_key"), table_name="webhook_event_log")
    op.drop_index(op.f("ix_webhook_event_log_event_type"), table_name="webhook_event_log")
    op.drop_table("webhook_event_log")
    op.drop_index(op.f("ix_sla_config_plan_type"), table_name="sla_config")
    op.drop_table("sla_config")
    op.drop_index(op.f("ix_kb_articles_slug"), table_name="kb_articles")
    op.drop_index(op.f("ix_kb_articles_category"), table_name="kb_articles")
    op.drop_table("kb_articles")
    op.drop_table("restaurants")
