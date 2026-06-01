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

### Infrastructure (Step 0.5+ / Phase 1)

<!-- TBD: DATABASE_URL, REDIS_URL, JWT_SECRET, TICKETING_PROVIDER, etc. -->

---

## Credential locations

| Credential | Where to obtain | Storage |
|------------|-----------------|---------|
| Chatwoot API token | Chatwoot UI → Profile → Access Token | `.env` locally; staging secrets manager TBD |
| Chatwoot account/inbox IDs | Chatwoot dashboard URL / Settings → Inboxes | `.env` |
| OpenAI API key | OpenAI platform dashboard | `.env` |

Never commit secrets. Reference by env var name only in docs and code.

---

## Local vs staging

| Setting | Local | Staging |
|---------|-------|---------|
| `CHATWOOT_BASE_URL` | `http://localhost:3000` | TBD (Step 0.5) |
| Database / Redis | TBD (Step 0.5 docker-compose) | TBD |
