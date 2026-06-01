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

### LLM (Step 0.2+)

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Step 0.2 | OpenAI API key (available per D-8) |
| `GOOGLE_API_KEY` | When available | Gemini API key (deferred per D-8) |
| `ANTHROPIC_API_KEY` | When available | Anthropic API key (deferred per D-8) |

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

<!-- TBD: REDIS_URL, JWT_SECRET, TICKETING_PROVIDER, etc. -->

---

## Credential locations

| Credential | Assumption | Where to obtain | Storage |
|------------|------------|-----------------|---------|
| Chatwoot API token | A4 | Chatwoot UI → Profile → Access Token | `.env` |
| Chatwoot account/inbox IDs | A4 | Chatwoot dashboard / Settings → Inboxes | `.env` |
| OpenAI API key | — | OpenAI platform dashboard | `.env` |
| Android repo access | A1 | ButterPOS mobile team — git URL or clone path | `.env` → `BUTTERPOS_ANDROID_REPO` |
| DB read access | A2 | ButterPOS backend team — read-only Postgres user | `.env` → `DATABASE_URL` |
| Data export file | A2 | ButterPOS backend team — CSV/JSON export | `.env` → `BUTTERPOS_DATA_EXPORT` |
| Billing API | A3 | ButterPOS backend/billing team — API docs + token | `.env` → `BILLING_API_URL` |
| MCP server | A5 | Backend teammate (Step 0.6) | `.env` → `MCP_SERVER_URL` |
| WhatsApp export | A6 | Support team — 3–6 month chat export | `.env` → `WHATSAPP_EXPORT_PATH` |

Never commit secrets. Reference by env var name only in docs and code.

---

## Local vs staging

| Setting | Local | Staging |
|---------|-------|---------|
| `CHATWOOT_BASE_URL` | `http://localhost:3000` | TBD (Step 0.5) |
| `DATABASE_URL` | TBD (Step 0.5 docker-compose) | TBD |
| ButterPOS production DB | Not used locally — export or read replica | TBD |

---

## Validation

Re-run assumption checks after updating credentials:

```bash
python spikes/0.4_assumption_validation/verify_assumptions.py
```

Reports saved to `spikes/0.4_assumption_validation/results/`.
