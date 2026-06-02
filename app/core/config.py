"""Application settings loaded from environment via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
TicketingProviderName = Literal["chatwoot"]


def _split_csv(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


class Settings(BaseSettings):
    """All configuration for the middleware. Secrets and tunables come from `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "ButterPOS Support Agent"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: LogLevel = "INFO"

    # HTTP server (local dev / smoke scripts)
    middleware_host: str = Field(
        default="0.0.0.0",
        description="Uvicorn bind host",
    )
    middleware_port: int = Field(
        default=8000,
        description="Uvicorn bind port",
    )
    middleware_base_url: str = Field(
        default="http://127.0.0.1:8000",
        description="Base URL for smoke/validation scripts",
    )

    # Infrastructure
    database_url: str = Field(
        default="postgresql+asyncpg://butterpos:butterpos@localhost:5432/butterpos",
        description="Async SQLAlchemy URL for middleware Postgres",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for cache, rate limits, PII token map, Celery broker",
    )

    # Celery worker / beat
    celery_timezone: str = Field(
        default="UTC",
        description="Celery timezone for beat schedules",
    )

    # Ticketing (Task 1.3+)
    ticketing_provider: TicketingProviderName = "chatwoot"
    chatwoot_base_url: str = ""
    chatwoot_api_token: str = ""
    chatwoot_account_id: int = 0
    chatwoot_inbox_id: int = 0
    chatwoot_agent_id: str = Field(
        default="",
        description="Optional agent user id for live assign_agent validation",
    )
    chatwoot_webhook_secret: str = ""
    chatwoot_request_timeout_seconds: float = Field(
        default=30.0,
        description="HTTP timeout for Chatwoot Application API calls",
    )
    chatwoot_max_retries: int = Field(
        default=3,
        description="Retry count for transient Chatwoot HTTP failures",
    )
    chatwoot_http_retry_backoff_max_seconds: float = Field(
        default=2.0,
        description="Max sleep between Chatwoot HTTP retries",
    )
    chatwoot_webhook_max_age_seconds: int = Field(
        default=300,
        description="Reject Chatwoot webhooks older than this many seconds (replay protection)",
    )
    chatwoot_webhook_subscriptions: str = Field(
        default=(
            "message_created,message_updated,conversation_status_changed,"
            "conversation_updated,webwidget_triggered"
        ),
        description="Comma-separated Chatwoot webhook event subscriptions",
    )

    # LLM via OpenRouter (D-11)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_app_url: str = ""
    openrouter_app_name: str = "ButterPOS Support Agent"
    llm_primary_model: str = "openai/gpt-4o"
    llm_fallback_model: str = "openai/gpt-4o-mini"
    llm_judge_model: str = "openai/gpt-4o-mini"

    # MCP (Task 1.x / Phase 2 agent loop)
    mcp_stub_server: str = "spikes/0.6_mcp_validation/stub_server/butterpos_stub_mcp.py"
    mcp_server_url: str = ""

    # Auth (Task 1.1 sub-step 2)
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    api_client_id: str = "butterpos-widget"
    api_client_secret: str = ""

    # PII masking (Task 1.1.7 — mandatory before LLM calls)
    pii_token_ttl_seconds: int = Field(
        default=86400,
        description="Redis TTL for reversible PII mask tokens (24h)",
    )
    pii_redis_key_prefix: str = "pii:token:"

    # Webhook DLQ (Task 1.4.3)
    webhook_dlq_redis_key: str = Field(
        default="webhook:dlq:pending",
        description="Redis sorted-set key for failed webhook retries",
    )
    webhook_dlq_max_attempts: int = Field(
        default=3,
        description="Total processing attempts before DLQ exhaustion alert",
    )
    webhook_dlq_retry_interval_seconds: int = Field(
        default=300,
        description="Seconds between DLQ retry sweeps (Celery beat schedule)",
    )

    # Webhook polling fallback (Task 1.4.4)
    webhook_polling_interval_seconds: int = Field(
        default=600,
        description="Celery beat interval for platform polling reconciliation",
    )
    webhook_polling_cursor_redis_key: str = Field(
        default="webhook:polling:last_sync_at",
        description="Redis key storing last successful poll unix timestamp",
    )
    webhook_polling_initial_lookback_seconds: int = Field(
        default=900,
        description="First poll lookback when no cursor exists",
    )

    # Ticketing read cache (Task 1.5.1)
    ticket_read_cache_ttl_seconds: int = Field(
        default=60,
        description="Redis TTL for cached StandardTicket reads",
    )
    contact_read_cache_ttl_seconds: int = Field(
        default=86400,
        description="Redis TTL for cached StandardContact reads (24h)",
    )
    ticket_read_cache_redis_prefix: str = Field(
        default="cache:ticket:",
        description="Redis key prefix for ticket read cache",
    )
    contact_read_cache_redis_prefix: str = Field(
        default="cache:contact:",
        description="Redis key prefix for contact read cache",
    )

    # Rate limits (Task 1.5.2)
    rate_limit_user_messages_per_hour: int = Field(
        default=20,
        description="Max incoming customer messages per user per hour",
    )
    rate_limit_user_window_seconds: int = Field(
        default=3600,
        description="Sliding window for user message rate limit",
    )
    rate_limit_user_redis_prefix: str = Field(
        default="ratelimit:user:",
        description="Redis key prefix for per-user message limits",
    )
    rate_limit_restaurant_messages_per_day: int = Field(
        default=100,
        description="Max incoming customer messages per restaurant per day",
    )
    rate_limit_restaurant_window_seconds: int = Field(
        default=86400,
        description="Sliding window for restaurant message rate limit",
    )
    rate_limit_restaurant_redis_prefix: str = Field(
        default="ratelimit:restaurant:",
        description="Redis key prefix for per-restaurant message limits",
    )
    rate_limit_restaurant_id_attribute_keys: str = Field(
        default="restaurant_id,butterpos_restaurant_id",
        description="Comma-separated conversation custom_attribute keys for restaurant scope",
    )

    # Request dedup (Task 1.5.3)
    request_dedup_redis_prefix: str = Field(
        default="dedup:request:",
        description="Redis key prefix for ticket-creation request dedup",
    )
    request_dedup_ttl_seconds: int = Field(
        default=86400,
        description="TTL for cached create_ticket results (24h)",
    )
    request_dedup_lock_ttl_seconds: int = Field(
        default=60,
        description="Redis lock TTL while create_ticket is in flight",
    )
    request_dedup_in_progress_poll_seconds: float = Field(
        default=0.05,
        description="Poll interval when waiting for peer create_ticket dedup",
    )
    request_dedup_in_progress_max_wait_seconds: float = Field(
        default=2.0,
        description="Max wait for peer create_ticket dedup result",
    )
    ticket_dedup_metadata_keys: str = Field(
        default="client_request_id,source_id,idempotency_key",
        description="Comma-separated metadata keys used for ticket creation dedup",
    )
    webhook_hot_dedup_redis_prefix: str = Field(
        default="dedup:webhook:",
        description="Redis key prefix for webhook idempotency hot-path",
    )
    webhook_hot_dedup_ttl_seconds: int = Field(
        default=86400,
        description="TTL for webhook hot dedup entries (24h)",
    )

    # Tenant data (Task 1.7)
    butterpos_data_export: str = Field(
        default="",
        description="Path to production tenant export JSON or CSV directory",
    )

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> str:
        if isinstance(value, str):
            return value.upper()
        return value

    @field_validator("chatwoot_account_id", "chatwoot_inbox_id", mode="before")
    @classmethod
    def empty_str_to_zero(cls, value: object) -> object:
        if value == "" or value is None:
            return 0
        return value

    def chatwoot_webhook_subscription_list(self) -> list[str]:
        return _split_csv(self.chatwoot_webhook_subscriptions)

    def rate_limit_restaurant_attribute_names(self) -> list[str]:
        return _split_csv(self.rate_limit_restaurant_id_attribute_keys)

    def ticket_dedup_metadata_key_list(self) -> list[str]:
        return _split_csv(self.ticket_dedup_metadata_keys)


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — use FastAPI dependency override in tests."""
    return Settings()
