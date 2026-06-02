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
    config.py             # Settings from `.env` (Task 1.1.1)
  api/
    deps.py               # FastAPI dependencies
    v1/                   # All routes under /api/v1/ (Task 1.1.3+)
  services/               # Business logic (Task 1.x+)
  providers/
    ticketing/            # TicketingProvider + adapters (Task 1.1.4, 1.3)
    llm/                  # LLMProvider + OpenRouter adapter (Phase 2+)
  models/                 # Pydantic Standard* + SQLAlchemy ORM (Task 1.1.5, 1.2)

tests/                    # pytest — mirror app modules
spikes/                   # Phase 0 experiments (not imported by app)
scripts/                  # Ops helpers (infra check, seeding)
docs/                     # Living documentation (update every step)
alembic/                  # DB migrations (Task 1.2)
```

**Rules:**

- Route handlers are thin — call **services** only.
- Core never imports Chatwoot, OpenAI, Anthropic, or Gemini SDKs directly.
- All HTTP endpoints live under `/api/v1/`.

---

## Running locally

```bash
# Install deps
pip install -r requirements.txt -r requirements-dev.txt

# Start infra (Postgres + Redis)
docker compose up -d

# Run API (Task 1.1+)
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

Customer/branch mapping (`Task 1.6`) requires **100% coverage** on mapping logic. Show `pytest --cov` output at the gate.

---

## Logging

Structured logging and global exception handler — **Task 1.1 sub-step 8**. Every request must log timestamp, `user_id`, `ticket_id` when available.
