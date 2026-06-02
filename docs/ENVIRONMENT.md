# Environment

Configuration, credentials, and environment-specific settings.

---

## Required env vars

### Chatwoot (Step 0.1+)

| Variable | Required | Description |
|----------|----------|-------------|
| `CHATWOOT_BASE_URL` | Step 0.1+ | Chatwoot instance URL, e.g. `http://localhost:3000` |
| `CHATWOOT_API_TOKEN` | Step 0.1+ | Agent API access token (Profile → Access Token) |
| `CHATWOOT_ACCOUNT_ID` | Step 0.1+ | Numeric account ID |
| `CHATWOOT_INBOX_ID` | Step 0.1+ | API-channel inbox ID |
| `CHATWOOT_WEBHOOK_SECRET` | Phase 1 | HMAC secret for inbound webhook verification |
| `CHATWOOT_WEBHOOK_MAX_AGE_SECONDS` | Optional | Replay window for webhook timestamps (default `300`) |
| `CHATWOOT_REQUEST_TIMEOUT_SECONDS` | Optional | HTTP timeout for Chatwoot API (default `30`) |
| `CHATWOOT_MAX_RETRIES` | Optional | Retries on transient Chatwoot failures (default `3`) |

### LLM (Step 0.2+ — via OpenRouter, D-11)

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | Step 0.2+ | OpenRouter API key — single gateway for all LLM vendors |
| `LLM_PRIMARY_MODEL` | Phase 1+ | Primary model slug, e.g. `openai/gpt-4o` |
| `LLM_FALLBACK_MODEL` | Phase 1+ | Fallback model slug, e.g. `openai/gpt-4o-mini` |
| `LLM_JUDGE_MODEL` | Eval | Fixed judge for Roman Urdu scoring, e.g. `openai/gpt-4o-mini` |
| `OPENROUTER_APP_URL` | Optional | Attribution URL for OpenRouter |
| `OPENROUTER_APP_NAME` | Optional | App name header (default: ButterPOS Support Agent) |
| `OPENROUTER_BASE_URL` | Optional | Default `https://openrouter.ai/api/v1` |

### Assumption validation (Step 0.4)

| Variable | Assumption | Description |
|----------|------------|-------------|
| `BUTTERPOS_ANDROID_REPO` | A1 | Git URL or local path to tablet/Android app repo |
| `DATABASE_URL` | A2 | PostgreSQL read connection (restaurant/branch/user tables) |
| `BUTTERPOS_DATA_EXPORT` | A2 | Alternative: path to CSV/JSON export of restaurant data |
| `BILLING_API_URL` | A3 | Billing API endpoint exposing plan/payment status |
| `BILLING_API_TOKEN` | A3 | Optional bearer token for billing API |
| `MCP_SERVER_URL` | A5 | Backend teammate's MCP server (Step 0.6) |
| `WHATSAPP_EXPORT_PATH` | A6 | Path to WhatsApp support history export (Step 0.3) |

### Infrastructure (Step 0.5+ / Phase 1)

| Variable | Required | Description |
|----------|----------|-------------|
| `POSTGRES_USER` | Step 0.5 | Postgres username (default: `butterpos`) |
| `POSTGRES_PASSWORD` | Step 0.5 | Postgres password (default: `butterpos`) |
| `POSTGRES_DB` | Step 0.5 | Database name (default: `butterpos`) |
| `POSTGRES_PORT` | Step 0.5 | Host port mapping (default: `5432`) |
| `DATABASE_URL` | Step 0.5+ | SQLAlchemy URL, e.g. `postgresql+asyncpg://butterpos:butterpos@localhost:5432/butterpos` |
| `REDIS_PORT` | Step 0.5 | Host port mapping (default: `6379`) |
| `REDIS_URL` | Step 0.5+ | Redis URL, e.g. `redis://localhost:6379/0` |
| `WEBHOOK_DLQ_REDIS_KEY` | Task 1.4.3 | DLQ sorted-set key (default `webhook:dlq:pending`) |
| `WEBHOOK_DLQ_MAX_ATTEMPTS` | Task 1.4.3 | Total processing tries before exhaustion alert (default `3`) |
| `WEBHOOK_POLLING_INTERVAL_SECONDS` | Task 1.4.4 | Beat interval for ticket reconciliation (default `600`) |
| `WEBHOOK_POLLING_CURSOR_REDIS_KEY` | Task 1.4.4 | Redis key for last poll timestamp |
| `WEBHOOK_POLLING_INITIAL_LOOKBACK_SECONDS` | Task 1.4.4 | First-run lookback when cursor absent (default `900`) |

### Application (Phase 1 — Task 1.1)

| Variable | Required | Description |
|----------|----------|-------------|
| `APP_NAME` | Optional | Display name (default: `ButterPOS Support Agent`) |
| `DEBUG` | Optional | FastAPI debug mode (default: `false`) |
| `LOG_LEVEL` | Optional | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `TICKETING_PROVIDER` | Phase 1 | Adapter to load (default: `chatwoot`) |
| `JWT_SECRET` | Task 1.1.2+ | HS256 signing secret for API tokens |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Optional | Token TTL (default: `60`) |
| `API_CLIENT_ID` | Task 1.1.2+ | Client id for token exchange (default: `butterpos-widget`) |
| `API_CLIENT_SECRET` | Task 1.1.2+ | Client secret for token exchange |

Settings class: `app/core/config.py` — loaded via `get_settings()`.

### PII masking (Task 1.1.7)

| Variable | Required | Description |
|----------|----------|-------------|
| `PII_TOKEN_TTL_SECONDS` | Optional | Redis TTL for mask tokens (default: `86400` = 24h) |
| `PII_REDIS_KEY_PREFIX` | Optional | Redis key prefix (default: `pii:token:`) |

Requires `REDIS_URL` for production reversible masking.

### Webhook DLQ (Task 1.4.3)

| Variable | Required | Description |
|----------|----------|-------------|
| `WEBHOOK_DLQ_REDIS_KEY` | Optional | Redis sorted-set for failed webhook retries |
| `WEBHOOK_DLQ_MAX_ATTEMPTS` | Optional | Max processing attempts (default `3`) |
| `WEBHOOK_DLQ_RETRY_INTERVAL_SECONDS` | Optional | Celery beat / retry delay in seconds (default `300`) |

Requires `REDIS_URL` for Celery broker and DLQ. Run worker + beat per `DEPLOYMENT.md`.

### Ticketing read cache (Task 1.5.1)

| Variable | Required | Description |
|----------|----------|-------------|
| `TICKET_READ_CACHE_TTL_SECONDS` | Optional | Cached `get_ticket` TTL (default `60`) |
| `CONTACT_READ_CACHE_TTL_SECONDS` | Optional | Cached contact lookup TTL (default `86400`) |
| `TICKET_READ_CACHE_REDIS_PREFIX` | Optional | Redis key prefix for tickets |
| `CONTACT_READ_CACHE_REDIS_PREFIX` | Optional | Redis key prefix for contacts |

### Webhook polling fallback (Task 1.4.4)

| Variable | Required | Description |
|----------|----------|-------------|
| `WEBHOOK_POLLING_INTERVAL_SECONDS` | Optional | Platform poll beat interval (default `600`) |
| `WEBHOOK_POLLING_CURSOR_REDIS_KEY` | Optional | Last poll cursor in Redis |
| `WEBHOOK_POLLING_INITIAL_LOOKBACK_SECONDS` | Optional | Initial lookback without cursor (default `900`) |
| `TICKET_READ_CACHE_TTL_SECONDS` | Optional | Redis TTL for cached ticket reads (default `60`) |
| `CONTACT_READ_CACHE_TTL_SECONDS` | Optional | Redis TTL for cached contact reads (default `86400`) |
| `TICKET_READ_CACHE_REDIS_PREFIX` | Optional | Ticket cache key prefix (default `cache:ticket:`) |
| `CONTACT_READ_CACHE_REDIS_PREFIX` | Optional | Contact cache key prefix (default `cache:contact:`) |

## Credential locations

| Credential | Assumption | Where to obtain | Storage |
|------------|------------|-----------------|---------|
| Chatwoot API token | A4 | Chatwoot UI → Profile → Access Token | `.env` |
| Chatwoot account/inbox IDs | A4 | Chatwoot dashboard / Settings → Inboxes | `.env` |
| JWT signing secret | Task 1.1.2 | Generate locally (`openssl rand -hex 32`) | `.env` → `JWT_SECRET` |
| API client credentials | Task 1.1.2 | Team Lead / deploy setup | `.env` → `API_CLIENT_ID`, `API_CLIENT_SECRET` |
| Android repo access | A1 | ButterPOS mobile team — git URL or clone path | `.env` → `BUTTERPOS_ANDROID_REPO` |
| DB read access | A2 | ButterPOS backend team — read-only Postgres user | `.env` → `DATABASE_URL` |
| Data export file | A2 | ButterPOS backend team — CSV/JSON export | `.env` → `BUTTERPOS_DATA_EXPORT` |
| Billing API | A3 | ButterPOS backend/billing team — API docs + token | `.env` → `BILLING_API_URL` |
| MCP stub server | A5 / Step 0.6 | Local stdio subprocess — `spikes/0.6_mcp_validation/stub_server/` | Path in repo (no secret) |
| MCP production server | A5 | Backend teammate (future) | `.env` → `MCP_SERVER_URL` |
| WhatsApp export | A6 | Support team — 3–6 month chat export | `.env` → `WHATSAPP_EXPORT_PATH` |

Never commit secrets. Reference by env var name only in docs and code.

---

## Local vs staging

| Setting | Local | Staging |
|---------|-------|---------|
| `CHATWOOT_BASE_URL` | `http://localhost:3000` | TBD — confirm VPS vs internal |
| `DATABASE_URL` | `postgresql+asyncpg://butterpos:butterpos@localhost:5432/butterpos` | TBD (Step 0.5 docker-compose locally; staging host TBD) |
| `REDIS_URL` | `redis://localhost:6379/0` | TBD |

---

## Validation

Re-run assumption checks after updating credentials:

```bash
python spikes/0.4_assumption_validation/verify_assumptions.py
```

Reports saved to `spikes/0.4_assumption_validation/results/`.
