# ButterPOS AI-Driven Customer Support System

Platform-agnostic middleware for an AI-powered customer support system. Orchestrates between a chatbot frontend, a ticketing platform (currently Zoho Desk, replaceable), an AI engine (RAG + LLM), and a knowledge base.

## Architecture

The ticketing platform is a **replaceable plugin** behind a `TicketingProvider` abstract interface. Switching platforms (Zoho → Freshdesk → Chatwoot) requires only a new adapter class and one config change.

## Tech Stack

- **Framework:** FastAPI (Python 3.11+)
- **Database:** PostgreSQL 15+
- **Cache / Queue:** Redis 7+
- **Task Queue:** Celery
- **AI:** OpenAI GPT-4o-mini / GPT-4o
- **ORM:** SQLAlchemy 2.0 (async)
- **Auth:** JWT

## Quick Start

```bash
# Copy environment config
cp .env.example .env
# Edit .env with your actual keys

# Start all services
make up

# Run migrations
make migrate

# Check health
curl http://localhost:8000/api/v1/health
```

## Development Commands

| Command | Description |
|---------|-------------|
| `make up` | Start all services (build + detach) |
| `make down` | Stop all services |
| `make logs` | Follow app logs |
| `make migrate` | Run database migrations |
| `make migrate-create msg="description"` | Create new migration |
| `make test` | Run test suite |
| `make lint` | Lint with ruff |
| `make format` | Format with ruff |
| `make db-shell` | PostgreSQL shell |
| `make redis-shell` | Redis CLI |
| `make seed` | Seed database |

## Services

| Service | Port | Description |
|---------|------|-------------|
| `app` | 8000 | FastAPI application |
| `db` | 5432 | PostgreSQL database |
| `redis` | 6379 | Redis cache & broker |
| `celery-worker` | — | Background task worker |
| `celery-beat` | — | Periodic task scheduler |
