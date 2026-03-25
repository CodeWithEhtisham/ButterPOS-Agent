from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "butterpos-support"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str
    API_VERSION: str = "v1"

    # Database
    DATABASE_URL: str
    DATABASE_URL_SYNC: str

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Ticketing Provider (THE KEY CONFIG)
    TICKETING_PROVIDER: str = "zoho"

    # Zoho (only loaded when provider=zoho)
    ZOHO_CLIENT_ID: str = ""
    ZOHO_CLIENT_SECRET: str = ""
    ZOHO_REFRESH_TOKEN: str = ""
    ZOHO_ORG_ID: str = ""
    ZOHO_API_BASE_URL: str = "https://desk.zoho.com/api/v1"
    ZOHO_ACCOUNTS_URL: str = "https://accounts.zoho.com"
    ZOHO_WEBHOOK_SECRET: str = ""

    # LLM
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL_PRIMARY: str = "gpt-4o-mini"
    OPENAI_MODEL_FALLBACK: str = "gpt-4o"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    ANTHROPIC_API_KEY: str = ""

    # Qdrant
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "kb_articles"

    # PII
    PII_MASK_TTL_SECONDS: int = 86400

    # Rate Limiting
    RATE_LIMIT_USER_PER_HOUR: int = 20
    RATE_LIMIT_RESTAURANT_PER_DAY: int = 100

    # LLM Cost
    LLM_MONTHLY_BUDGET_USD: float = 500.0
    LLM_BUDGET_ALERT_THRESHOLD: float = 0.8
    LLM_BUDGET_SOFT_CAP: float = 0.95
    LLM_BUDGET_HARD_CAP: float = 1.0

    # JWT
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""

    # Circuit Breaker
    CIRCUIT_BREAKER_REOPEN_THRESHOLD: float = 0.4
    CIRCUIT_BREAKER_AGENT_FLAG_THRESHOLD: int = 3
    CIRCUIT_BREAKER_CONFIDENCE_FLOOR: int = 45

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
