# Deployment

Infrastructure, containers, CI/CD, and operational runbooks.

---

## Overview

| Component | Purpose | Phase |
|-----------|---------|-------|
| **PostgreSQL 15** | System of record — tickets, conversations, KB, audit logs | 0.5+ |
| **Redis 7** | Cache, rate limits, PII token map, Celery broker, webhook DLQ | 0.5+ |
| **Docker Compose** | Local dev + staging infra | 0.5 |
| **GitHub Actions** | CI — lint, test, infra check on every push | 0.5 |

Chatwoot runs separately (Step 0.1 — local Docker per team setup).

---

## Infrastructure

### Server requirements (staging / production)

| Requirement | Minimum |
|-------------|---------|
| OS | Ubuntu 22.04 LTS or later |
| CPU | 2 vCPU |
| RAM | 4 GB (8 GB recommended with Chatwoot on same host) |
| Disk | 20 GB SSD |
| Docker | Docker Engine 24+ with Compose v2 (`docker compose`) |

### Ubuntu 22.04+ prep notes

```bash
# Docker (official convenience script — verify on your host policy)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in

# Clone repo
git clone <repo-url> butterpos-agent && cd butterpos-agent
cp .env.example .env   # fill secrets locally — never commit

# Start infra
docker compose up -d
docker compose ps        # both services should be "healthy"
python scripts/check_infra.py
```

**Server target:** TBD — confirm internal vs VPS with team lead before production deploy. SSH access and host details are out of band (not stored in repo).

---

## Docker Compose

File: [`docker-compose.yml`](../docker-compose.yml)

| Service | Image | Port | Volume |
|---------|-------|------|--------|
| `postgres` | `postgres:15-alpine` | 5432 | `postgres_data` |
| `redis` | `redis:7-alpine` | 6379 | `redis_data` |

```bash
docker compose up -d      # start
docker compose down       # stop (data persists in volumes)
docker compose down -v    # stop + wipe data
docker compose logs -f    # tail logs
```

Health checks: `pg_isready` (Postgres), `redis-cli ping` (Redis).

### Database migrations (Task 1.2.6)

After `docker compose up -d` and `.env` is configured:

```bash
pip install -r requirements.txt
alembic upgrade head
alembic current
```

| Command | Purpose |
|---------|---------|
| `alembic upgrade head` | Apply all pending migrations |
| `alembic downgrade -1` | Roll back one revision |
| `alembic revision --autogenerate -m "msg"` | Generate migration from ORM diff |
| `alembic history` | List revision chain |

Initial revision `20260602_0001` creates all nine middleware tables. App runtime uses asyncpg; Alembic uses psycopg2 via `app/db/url.py`.

---

- **Postgres** — durable state: ticket cache mirror, AI conversation history, KB articles, webhook audit log, SLA config. Required for audit trail and Phase 1 migrations (Alembic).
- **Redis** — ephemeral/fast: 60s ticket cache, 24h contact cache, PII mask token map (24h TTL), rate limiting sliding windows, Celery task queue, webhook DLQ. Keeps hot paths off Postgres and supports sub-second invalidation on webhooks.

---

## CI/CD

Workflow: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)

**Triggers:** push/PR to `main`, `staging`, `phase-0`

**Job steps:**

1. **Lint** — `ruff check spikes/ scripts/ tests/`
2. **Test** — `pytest tests/` (structure smoke + optional connectivity if env set)
3. **Infra check** — `python scripts/check_infra.py` against CI service containers (Postgres 15 + Redis 7)

CI uses GitHub Actions service containers — same images as local `docker-compose.yml`.

**Celery (Task 1.4.3):**

```bash
# Terminal 1 — task worker
celery -A app.worker.celery_app worker -l info

# Terminal 2 — beat (DLQ retry + ticket polling)
celery -A app.worker.celery_app beat -l info
```

Beat schedules: `webhook.retry_dlq` (5 min), `ticket.poll_reconcile` (10 min).

Broker and DLQ both use `REDIS_URL`.

**Not yet in CI (Phase 1+):** middleware app build, Alembic migrate, Chatwoot integration tests, coverage gate for mapping module.

---

## Data seeding

**Task 1.7** — load restaurant / branch / user data from ButterPOS export into middleware Postgres.

### Prerequisites

- Migrations applied: `alembic upgrade head`
- `DATABASE_URL` set in `.env`
- Export file from ButterPOS team **or** local demo fixture

### Demo fixture (local dev only)

```bash
python scripts/seed_data.py \
  --input scripts/fixtures/sample_tenant_export.json \
  --dry-run

python scripts/seed_data.py \
  --input scripts/fixtures/sample_tenant_export.json
```

### Production export

Set `BUTTERPOS_DATA_EXPORT` in `.env` to the signed-off JSON or CSV directory path, then:

```bash
python scripts/seed_data.py --input "$BUTTERPOS_DATA_EXPORT"
```

| Flag | Purpose |
|------|---------|
| `--dry-run` | Validate export only — no DB writes |
| `--seed-default-sla` | Insert default `sla_config` rows for `8h` / `16h` / `24-7` when omitted |

Export schema: `DATA_MODELS.md` § Tenant export schema. Upserts by `butterpos_*` external ids — safe to re-run.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `connection refused` on 5432 | `docker compose up -d` — wait for healthy status |
| `password authentication failed` | Match `DATABASE_URL` credentials to `POSTGRES_*` in `.env` |
| Port 5432/6379 already in use | Set `POSTGRES_PORT=15432` and `REDIS_PORT=16379` in `.env`, update `DATABASE_URL` / `REDIS_URL` |
| CI infra check fails | Verify service container health in Actions log |

See also [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).
