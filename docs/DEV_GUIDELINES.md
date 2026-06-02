# Developer Guidelines

Coding standards, project layout, testing, and logging conventions.

---

## Stack

- **Python 3.11+**, async-first
- **FastAPI** + **Pydantic v2** + **pydantic-settings**
- **SQLAlchemy 2** (async) + **Alembic** — Task 1.2+
- **Redis** — cache, rate limits, PII token map — Task 1.5+
- **Celery** — webhook DLQ, polling fallback — Task 1.4+
- **pytest** + **ruff** for CI

---

## Project layout

```
app/
  main.py                 # FastAPI factory (`create_app`)
  core/
    config.py
    context.py
    logging_config.py
    error_handlers.py
    exceptions.py
    pii/
    security.py
  db/                     # SQLAlchemy ORM + async session (Task 1.2+)
    base.py               # Base + TimestampMixin
    session.py            # async engine + get_async_session()
    models/               # ORM table classes (Task 1.2.2+)
  api/
    deps.py               # FastAPI dependencies
    middleware/           # Request logging middleware
    v1/                   # All routes under /api/v1/
  services/               # Business logic
  providers/
    ticketing/            # TicketingProvider + adapters
    llm/                  # LLMProvider (Phase 2+)
  models/                 # Pydantic Standard* + ORM (Task 1.2+)
  schemas/                # API request/response schemas

tests/
spikes/
scripts/
docs/
alembic/                  # Task 1.2+
```

**Rules:**

- Route handlers are thin — call **services** only.
- Core never imports Chatwoot, OpenAI, Anthropic, or Gemini SDKs directly.
- All HTTP endpoints live under `/api/v1/`.

---

## Running locally

```bash
pip install -r requirements.txt -r requirements-dev.txt
docker compose up -d
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Testing

```bash
pytest tests/ -v
ruff check app/ tests/ spikes/ scripts/
```

Use `get_settings.cache_clear()` in tests when overriding env vars for the cached singleton.

---

## Coverage rules

Customer/branch mapping (`Task 1.6`) requires **100% coverage** on mapping logic. Gate command:

```bash
pytest tests/test_customer_mapping.py -q \
  --cov=app.services.mapping \
  --cov=app.services.customer_mapping_service \
  --cov=app.repositories.customer_mapping_repository \
  --cov-report=term-missing \
  --cov-fail-under=100
```

---

## Logging

**Task 1.1.8** — JSON structured logs to stdout; every HTTP request logged with correlation context.

### Log format

Each line is a JSON object:

```json
{
  "timestamp": "2026-06-02T12:00:00+00:00",
  "level": "INFO",
  "logger": "app.request",
  "message": "request_completed method=GET path=/api/v1/auth/me ...",
  "request_id": "uuid",
  "user_id": "staff-123",
  "ticket_id": null,
  "method": "GET",
  "path": "/api/v1/auth/me",
  "status_code": 200,
  "duration_ms": 4.2
}
```

### Request context

| Field | Source |
|-------|--------|
| `request_id` | Generated per request; returned as `X-Request-ID` header |
| `user_id` | JWT `sub` when Bearer token present and valid |
| `ticket_id` | Path `ticket_id` / `provider_ticket_id` or query `ticket_id` |

Services may call `set_ticket_id()` from `app.core.context` when ticket is resolved later in the handler.

### Modules

| Module | Role |
|--------|------|
| `app/core/logging_config.py` | JSON formatter + `configure_logging()` |
| `app/core/context.py` | `contextvars` for request scope |
| `app/api/middleware/request_logging.py` | Per-request access logs |
| `app/core/error_handlers.py` | Global HTTP / AppError / 500 handlers |
| `app/core/exceptions.py` | `AppError` base class |

### Rules

- Never log cleartext PII or Redis mask token values.
- Unhandled errors return generic `"Internal server error"` unless `DEBUG=true`.
- Set `LOG_LEVEL` in `.env` (default `INFO`).
