# Environment

Configuration is **centralized in `.env`**. The app loads every tunable through `app/core/config.py` (`Settings` via pydantic-settings). Copy [`.env.example`](../.env.example) to `.env` and edit one file — no need to hunt through code.

**Quick reference:** see `.env.example` for the full list with defaults. Below: grouped tables for documentation.

---

## Required env vars

### Chatwoot (Step 0.1+)

| Variable | Required | Description |
|----------|----------|-------------|
| `CHATWOOT_BASE_URL` | Step 0.1+ | Chatwoot instance URL, e.g. `http://localhost:3000` |
| `CHATWOOT_API_TOKEN` | Step 0.1+ | Agent API access token (Profile → Access Token) |
| `CHATWOOT_ACCOUNT_ID` | Step 0.1+ | Numeric account ID |
| `CHATWOOT_INBOX_ID` | Step 0.1+ | API-channel inbox ID |
| `CHATWOOT_AGENT_ID` | Optional | Agent user id for live `assign_agent` validation (Task 1.8.2) |
| `CHATWOOT_WEBHOOK_SECRET` | Phase 1 | HMAC secret for inbound webhook verification |
| `CHATWOOT_WEBHOOK_CALLBACK_URL` | Optional | URL Chatwoot POSTs to; use `http://host.docker.internal:8000/api/v1/webhooks/chatwoot` when Chatwoot is in Docker |
| `CHATWOOT_WEBHOOK_MAX_AGE_SECONDS` | Optional | Replay window for webhook timestamps (default `300`) |
| `CHATWOOT_WEBHOOK_SUBSCRIPTIONS` | Optional | Comma-separated events to register (see `.env.example`) |
| `CHATWOOT_HTTP_RETRY_BACKOFF_MAX_SECONDS` | Optional | Max sleep between Chatwoot HTTP retries (default `2`) |
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

### Inbound message rate limits (Task 1.5.2)

| Variable | Required | Description |
|----------|----------|-------------|
| `RATE_LIMIT_USER_MESSAGES_PER_HOUR` | Optional | Per-user incoming message cap (default `20`) |
| `RATE_LIMIT_USER_WINDOW_SECONDS` | Optional | User sliding window (default `3600`) |
| `RATE_LIMIT_USER_REDIS_PREFIX` | Optional | Redis key prefix (default `ratelimit:user:`) |
| `RATE_LIMIT_RESTAURANT_MESSAGES_PER_DAY` | Optional | Per-restaurant incoming message cap (default `100`) |
| `RATE_LIMIT_RESTAURANT_WINDOW_SECONDS` | Optional | Restaurant sliding window (default `86400`) |
| `RATE_LIMIT_RESTAURANT_REDIS_PREFIX` | Optional | Redis key prefix (default `ratelimit:restaurant:`) |
| `RATE_LIMIT_RESTAURANT_ID_ATTRIBUTE_KEYS` | Optional | Comma-separated custom_attribute keys for restaurant scope |

Requires `REDIS_URL` for production rate limiting. Outgoing messages and non-`message_created` events are not counted.

### Request dedup (Task 1.5.3)

| Variable | Required | Description |
|----------|----------|-------------|
| `REQUEST_DEDUP_REDIS_PREFIX` | Optional | Redis key prefix for ticket-creation dedup (default `dedup:request:`) |
| `REQUEST_DEDUP_TTL_SECONDS` | Optional | Cached `create_ticket` result TTL (default `86400`) |
| `REQUEST_DEDUP_LOCK_TTL_SECONDS` | Optional | In-flight create_ticket lock TTL (default `60`) |
| `REQUEST_DEDUP_IN_PROGRESS_POLL_SECONDS` | Optional | Poll interval when waiting on peer dedup (default `0.05`) |
| `REQUEST_DEDUP_IN_PROGRESS_MAX_WAIT_SECONDS` | Optional | Max wait for peer dedup (default `2`) |
| `TICKET_DEDUP_METADATA_KEYS` | Optional | Comma-separated metadata keys for ticket dedup |
| `WEBHOOK_HOT_DEDUP_REDIS_PREFIX` | Optional | Redis hot-path prefix for webhook idempotency (default `dedup:webhook:`) |
| `WEBHOOK_HOT_DEDUP_TTL_SECONDS` | Optional | Hot webhook dedup TTL (default `86400`) |

### Celery / beat schedules

| Variable | Required | Description |
|----------|----------|-------------|
| `CELERY_TIMEZONE` | Optional | Celery timezone (default `UTC`) |
| `WEBHOOK_DLQ_RETRY_INTERVAL_SECONDS` | Optional | DLQ retry beat interval (default `300` = 5 min) |
| `WEBHOOK_POLLING_INTERVAL_SECONDS` | Optional | Ticket polling beat interval (default `600` = 10 min) |

### HTTP server / scripts

| Variable | Required | Description |
|----------|----------|-------------|
| `MIDDLEWARE_HOST` | Optional | Uvicorn bind host (default `0.0.0.0`) |
| `MIDDLEWARE_PORT` | Optional | Uvicorn bind port (default `8000`) |
| `MIDDLEWARE_BASE_URL` | Optional | Base URL for smoke/validation scripts |

### MCP / chat (remote MCP server)

| Variable | Required | Description |
|----------|----------|-------------|
| `MCP_SERVER_URL` | Chat enabled | Remote MCP endpoint, e.g. `http://localhost:3001/mcp` |
| `MCP_TRANSPORT` | Optional | `streamable_http` (default) or `sse` |
| `AGENT_DEFAULT_BRANCH_ID` | Optional | Default branch for MCP tool calls (default `demo-branch-karachi`) |
| `AGENT_MAX_TOOL_ROUNDS` | Optional | Max LLM↔tool loops per chat message (default `6`) |
| `AGENT_INBOUND_ENABLED` | Optional | Run agent on inbound Chatwoot webhooks (default `true`) |

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
| MCP spike (Phase 0) | A5 / Step 0.6 | Local stdio — `spikes/0.6_mcp_validation/stub_server/` | Path in repo (no secret) |
| MCP production server | A5 | Backend teammate — HTTP endpoint | `.env` → `MCP_SERVER_URL` |
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

### Assumption checks (Phase 0)

```bash
python spikes/0.4_assumption_validation/verify_assumptions.py
```

Reports saved to `spikes/0.4_assumption_validation/results/`.

### Phase 1 exit scripts

```bash
python scripts/check_infra.py
python scripts/smoke_middleware.py
python scripts/validate_chatwoot.py
python scripts/validate_seed.py
```

See `DEPLOYMENT.md` § Phase 1 verification checklist.
