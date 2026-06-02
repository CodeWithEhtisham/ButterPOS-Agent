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

Workflow: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) — **currently commented out** in repo; re-enable before production CI gate.

**Intended triggers:** push/PR to `main`, `staging`, `phase-0`

**Intended job steps:**

1. **Lint** — `ruff check app/ tests/ spikes/ scripts/`
2. **Test** — `pytest tests/`
3. **Infra check** — `python scripts/check_infra.py` against service containers (Postgres 15 + Redis 7)

**Phase 1 local gates (manual until CI re-enabled):**

| Gate | Command |
|------|---------|
| Unit + integration tests | `pytest tests/ -q` |
| Mapping 100% coverage | See `DEV_GUIDELINES.md` |
| Infra | `python scripts/check_infra.py` |
| Middleware smoke | `python scripts/smoke_middleware.py` |
| Chatwoot live | `python scripts/validate_chatwoot.py` |
| Seed validation | `python scripts/validate_seed.py` |

**Celery (Task 1.4.3):**

```bash
# Terminal 1 — task worker
celery -A app.worker.celery_app worker -l info

# Terminal 2 — beat (DLQ retry + ticket polling)
celery -A app.worker.celery_app beat -l info
```

Beat schedules: `webhook.retry_dlq` (5 min), `ticket.poll_reconcile` (10 min).

Broker and DLQ both use `REDIS_URL`.

---

## Phase 1 verification checklist (Task 1.8)

Complete locally before Phase 2. All scripts assume repo root and loaded `.env`.

| Step | Command | Pass criteria |
|------|---------|---------------|
| 1 | `python scripts/check_infra.py` | Postgres + Redis OK |
| 2 | `alembic upgrade head` | Migrations applied |
| 3 | `python scripts/seed_data.py --input scripts/fixtures/sample_tenant_export.json` | Upsert completes |
| 4 | `python scripts/validate_seed.py` | `RESULT: PASS` |
| 5 | `uvicorn app.main:app --port 8000` | Server starts |
| 6 | `python scripts/smoke_middleware.py` | `RESULT: PASS` |
| 7 | `python scripts/validate_chatwoot.py --middleware-url http://127.0.0.1:8000` | `RESULT: PASS` |
| 8 | `pytest tests/ -q` | All tests pass |
| 9 | Mapping coverage gate | 100% on mapping modules (see `DEV_GUIDELINES.md`) |

**Signed off (local demo):** 2026-06-02 — steps 1–8 PASS on developer machine. Production tenant export and CI re-enable remain open.

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

### Post-seed validation (Task 1.7.2)

After seeding, run automated mapping and row-count checks:

```bash
python scripts/validate_seed.py
python scripts/validate_seed.py --json   # machine-readable report
```

**Expected demo fixture result:** `RESULT: PASS` with checks for restaurants/branches/users/sla_configs and mapping scenarios (`active`, `payment_due`, `no_branch`, contact lookup, unknown user).

| Check | Demo expectation |
|-------|------------------|
| `demo-user-active` | `active`, tier 3 |
| `demo-user-unpaid` | `payment_due`, tier 1 |
| `demo-user-no-branch` | `no_branch`, tier 1 |
| Contact `9001` / `9002` | `active` / `payment_due` |
| Unknown user | `unknown_user` |

### Sign-off checklist

| Step | Owner | Demo (2026-06-02) | Production |
|------|-------|-------------------|------------|
| Export schema agreed (`export_schema_version: 1`) | ButterPOS + middleware | ✓ fixture | Pending real export |
| `seed_data.py --dry-run` passes | Middleware | ✓ | Pending |
| `seed_data.py` upsert completes | Middleware | ✓ | Pending |
| `validate_seed.py` → PASS | Middleware | ✓ | Pending |
| Spot-check 3+ real users in Chatwoot/mapping | Both teams | N/A (fixture ids) | Pending |
| Production export path in `BUTTERPOS_DATA_EXPORT` | ButterPOS team | N/A | Pending |

**Signed off (demo):** automated validation PASS against `scripts/fixtures/sample_tenant_export.json` on local Postgres (2026-06-02).

**Production gate:** repeat seed + `validate_seed.py` when ButterPOS delivers production export; extend `DEMO_USER_EXPECTATIONS` in `tenant_validation_service.py` or add a production expectations file.

---

## Running the middleware (Task 1.8.1)

### Start dependencies

Postgres and Redis must be reachable (`DATABASE_URL`, `REDIS_URL` in `.env`). If using Docker for infra and port 5432 is free:

```bash
docker compose up -d
alembic upgrade head
```

If port 5432 is already in use (system Postgres), point `DATABASE_URL` at that instance instead.

### Start the app

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

OpenAPI: `http://127.0.0.1:8000/docs`

### Smoke test

With the app running:

```bash
python scripts/smoke_middleware.py
python scripts/smoke_middleware.py --base-url http://127.0.0.1:8000 --skip-infra
```

**Expected:** `RESULT: PASS` — infra (optional), `/openapi.json`, `/api/v1/system/health`, JWT token + `/auth/me`.

| Check | Meaning |
|-------|---------|
| `system_health` | Postgres + Redis wired through FastAPI lifespan |
| `auth_token` / `auth_me` | JWT auth path works |

### ChatwootAdapter live validation (Task 1.8.2)

Requires local Chatwoot running with `CHATWOOT_*` vars in `.env`.

```bash
python scripts/validate_chatwoot.py
python scripts/validate_chatwoot.py --middleware-url http://127.0.0.1:8000
python scripts/validate_chatwoot.py --json
```

**Expected:** `RESULT: PASS` — adapter `health_check`, contact, ticket CRUD, comment, note, tags, status update. Optional `assign_agent` when `CHATWOOT_AGENT_ID` is set. With `--middleware-url`, also probes `GET /api/v1/system/ticketing-health` through the factory stack.

| Check | Meaning |
|-------|---------|
| `health_check` | Direct Chatwoot Application API probe |
| `create_ticket` … `update_status` | Full `TicketingProvider` round-trip |
| `middleware_ticketing_health` | Adapter wired through FastAPI + JWT |

Creates a test contact/conversation in Chatwoot (safe to delete manually).

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `connection refused` on 5432 | `docker compose up -d` — wait for healthy status |
| `password authentication failed` | Match `DATABASE_URL` credentials to `POSTGRES_*` in `.env` |
| Port 5432/6379 already in use | Set `POSTGRES_PORT=15432` and `REDIS_PORT=16379` in `.env`, update `DATABASE_URL` / `REDIS_URL` |
| CI infra check fails | Verify service container health in Actions log |

See also [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).
