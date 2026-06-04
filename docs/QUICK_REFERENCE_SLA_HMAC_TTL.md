# Quick reference: SLA, HMAC, TTL, and related security patterns

Small cheat sheet for **what they mean**, **why ButterPOS uses them**, and **how to test locally**.

> **Yes — there is more in the code** than SLA / HMAC / 24h PII. Section 4 lists other patterns people often miss (JWT, rate limits, dedup, DLQ, caches, tiers).

---

## 1. SLA (Service Level Agreement)

### What it stands for

**SLA** = promised support rules per customer plan: coverage hours, response targets, and when to auto-escalate.

### What it is in this project

| Piece | Where | Purpose |
|-------|--------|---------|
| `sla_config` table | Postgres | One row per plan type (`8h`, `16h`, `24-7`) |
| Mapping evaluator | `app/services/mapping/evaluator.py` | Turns user → branch → restaurant → plan into `ACTIVE`, `OUTSIDE_COVERAGE`, `PLAN_EXPIRED`, etc. |
| Agent tier cap | Same evaluator | e.g. payment due / outside hours → Tier 1 (read-only) |

Typical fields (from seed export):

| Field | Meaning |
|-------|---------|
| `coverage_hours` | How many hours per day support is offered (8, 16, or 24) |
| `first_response_minutes` | Target time for first reply |
| `resolution_minutes` | Target time to resolve or escalate |
| `escalation_after_minutes` | Auto-escalate if ticket open longer than this |
| `rules.coverage_start_hour` | Local day start (e.g. 9 = 09:00 in branch timezone) |

**Not the same as** chat escalation to Chatwoot (keyword “human agent”) — SLA is **business rules** from tenant data; escalation to human is a **product flow**.

### How to test SLA

**Prerequisites:** Postgres up, data seeded.

```bash
# Seed tenant + SLA rows (if empty DB)
python scripts/seed_data.py --fixture scripts/fixtures/sample_tenant_export.json --seed-default-sla

# Validate mapping scenarios (includes SLA / coverage checks)
python scripts/validate_seed.py

# Same, JSON output
python scripts/validate_seed.py --json

# Test “outside 8h window” at a specific time
python scripts/validate_seed.py --at "2026-06-02T22:00:00+00:00"
```

**Unit tests (fast, no DB):**

```bash
pytest tests/test_customer_mapping.py -q
```

**What to look for:** `validate_seed.py` prints pass/fail per scenario (active plan, expired, unpaid, 8h/16h/24-7, unknown user, no branch). Mapping tests assert `within_coverage` true/false for plan types.

---

## 2. HMAC (webhook signature)

### What it stands for

**HMAC** = *Hash-based Message Authentication Code*. Here: **Chatwoot signs each webhook** so middleware can prove the POST really came from Chatwoot and was not tampered with.

### What it is in this project

| Item | Value |
|------|--------|
| Endpoint | `POST /api/v1/webhooks/chatwoot` |
| Auth | **HMAC only** (no JWT on this route) |
| Secret | `CHATWOOT_WEBHOOK_SECRET` in `.env` (from webhook registration) |
| Headers | `X-Chatwoot-Signature`, `X-Chatwoot-Timestamp` |
| Formula | `sha256=HMAC-SHA256(secret, "{timestamp}.{raw_json_body}")` |
| Max age | `CHATWOOT_WEBHOOK_MAX_AGE_SECONDS` (default **300** = 5 minutes) |

Implementation: `app/providers/ticketing/chatwoot/webhooks.py` → `verify_chatwoot_webhook()`.

**Used for:** Trusting inbound Chatwoot events (new messages, status changes) before Celery processes them (agent reply, human relay to widget).

### How to test HMAC

**1) Register webhook and set secret**

```bash
python scripts/register_chatwoot_webhook.py --docker-host   # or without flag if both on host
# Copy secret into .env → CHATWOOT_WEBHOOK_SECRET
# Restart uvicorn + Celery worker
```

**2) Automated tests**

```bash
pytest tests/test_chatwoot_webhooks.py tests/test_webhook_receiver.py -q
```

**3) Manual signed curl** (from repo root, with venv):

```bash
python - <<'PY'
import json, time, httpx
from app.providers.ticketing.chatwoot.webhooks import compute_chatwoot_signature

secret = "YOUR_CHATWOOT_WEBHOOK_SECRET"  # from .env
payload = {
    "event": "message_created",
    "id": 99999,
    "content": "HMAC test",
    "message_type": "incoming",
    "created_at": "2026-06-03T12:00:00Z",
    "sender": {"id": 1, "type": "contact"},
    "conversation": {"id": 1},
}
body = json.dumps(payload).encode()
ts = str(int(time.time()))
headers = {
    "Content-Type": "application/json",
    "X-Chatwoot-Timestamp": ts,
    "X-Chatwoot-Signature": compute_chatwoot_signature(secret, ts, body),
}
r = httpx.post("http://127.0.0.1:8000/api/v1/webhooks/chatwoot", content=body, headers=headers)
print(r.status_code, r.text)
PY
```

**Expect:** `200` and `"status":"accepted"` (or `duplicate` on replay).  
**Wrong secret or missing headers:** `401` / rejected.

---

## 3. 24h TTL (PII token lifetime)

### What it stands for

**TTL** = *Time To Live* — how long something is kept before it expires.

**24h TTL** here = **86400 seconds** — how long masked PII placeholders stay reversible in Redis.

### What it is in this project

| Item | Detail |
|------|--------|
| Env | `PII_TOKEN_TTL_SECONDS=86400` (24 × 60 × 60) |
| Redis keys | `pii:token:{id}` → original phone/email/name |
| Flow | Before LLM: mask → send tokens to OpenRouter. After LLM: unmask for user/Chatwoot |
| Why | Paid cloud LLMs must not receive raw customer PII (V1 policy) |

Implementation: `app/core/pii/masker.py`, `app/core/pii/store.py`.

**86400** also appears elsewhere (e.g. contact cache TTL) — always read the env name; **PII** specifically uses `PII_TOKEN_TTL_SECONDS`.

### How to test 24h PII TTL

**1) Unit tests**

```bash
pytest tests/test_pii_masker.py tests/test_pii_store.py -q
```

**2) Quick manual check (Redis + masker)**

```bash
# Redis must be running (docker compose up -d)
python - <<'PY'
import asyncio
from app.core.config import get_settings
from app.core.pii.masker import PIIMasker
from app.core.pii.store import RedisPiiTokenStore

async def main():
    s = get_settings()
    print("TTL seconds:", s.pii_token_ttl_seconds)  # expect 86400
    store = RedisPiiTokenStore(s)
    masker = PIIMasker(store)
    text = "Call me at 0301-1234567 or ali@example.com"
    masked = await masker.mask(text)
    print("Masked:", masked.masked_text)
    restored = await masker.unmask(masked.masked_text)
    print("Unmasked:", restored)
    assert "0301" in restored or "ali@" in restored
    print("OK — round-trip works")
asyncio.run(main())
PY
```

**3) See TTL in Redis**

```bash
redis-cli KEYS 'pii:token:*'
redis-cli TTL pii:token:SOME_ID_FROM_MASKED_TEXT
# Should be ≤ 86400 (counts down from set time)
```

**After 24h:** unmask may leave tokens unreplaced if Redis expired the key — by design for privacy retention limit.

---

## Quick comparison (the three you asked about)

| Term | Layer | Protects / governs |
|------|--------|---------------------|
| **SLA** | Business / tenant DB | *Who* gets support *when* and agent tier |
| **HMAC** | Webhook transport | *Who* sent the Chatwoot POST (integrity + authenticity) |
| **24h TTL** | PII / Redis | *How long* we keep reversible masks for LLM calls |

---

## 4. Other similar things in the code (often missed)

These use the **same ideas** (TTL, secrets, limits, dedup) but different names and env vars.

### JWT (API auth — not HMAC)

| Item | Detail |
|------|--------|
| **Stands for** | JSON Web Token |
| **Used for** | Chat UI / widget calling middleware (`POST /api/v1/chat/messages`, poll session, etc.) |
| **Not used for** | Chatwoot webhooks (those use HMAC only) |
| **Env** | `JWT_SECRET`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default **60 min**, not 24h) |
| **Bootstrap** | `API_CLIENT_ID` + `API_CLIENT_SECRET` → `POST /api/v1/auth/token` |
| **Code** | `app/core/security.py`, `app/api/deps.py` |

**Test:** `pytest tests/test_auth.py -q`  
**Manual:** Chat test UI → Get token; or `curl` token endpoint (see `docs/API_SPEC.md`).

---

### Webhook timestamp window (5 minutes — not 24h)

| Item | Detail |
|------|--------|
| **Env** | `CHATWOOT_WEBHOOK_MAX_AGE_SECONDS=300` |
| **Used for** | Reject old/replayed webhook timestamps (with HMAC) |
| **Code** | `verify_chatwoot_webhook()` in `app/providers/ticketing/chatwoot/webhooks.py` |

**Test:** `pytest tests/test_chatwoot_webhooks.py -q` (stale timestamp cases).

---

### Webhook idempotency (duplicate events)

| Item | Detail |
|------|--------|
| **Used for** | Same Chatwoot event POSTed twice → process once |
| **Postgres** | `webhook_event_log` + unique `idempotency_key` |
| **Redis hot path** | `WEBHOOK_HOT_DEDUP_*` — TTL **86400** (24h) |
| **Code** | `app/services/webhook_service.py` |

**Test:** `pytest tests/test_webhook_idempotency.py tests/test_webhook_receiver.py -q`

---

### Rate limits (inbound customer messages)

| Item | Detail |
|------|--------|
| **Used for** | Abuse protection on webhook `message_created` |
| **Per user** | `RATE_LIMIT_USER_MESSAGES_PER_HOUR` / window **3600s** (1 hour) |
| **Per restaurant** | `RATE_LIMIT_RESTAURANT_MESSAGES_PER_DAY` / window **86400s** (24h) |
| **Code** | `app/core/rate_limit/inbound_message_limits.py` |

**Test:** `pytest tests/test_rate_limits.py -q`  
**Symptom:** Webhook returns `rate_limited` in JSON body.

---

### Request dedup (create Chatwoot ticket twice)

| Item | Detail |
|------|--------|
| **Used for** | Client retries `create_ticket` with same `client_request_id` → one conversation |
| **Env** | `REQUEST_DEDUP_TTL_SECONDS=86400`, lock `REQUEST_DEDUP_LOCK_TTL_SECONDS=60` |
| **Code** | `app/providers/ticketing/deduping_adapter.py` |

**Test:** `pytest tests/test_request_dedup.py -q`

---

### Webhook DLQ (dead letter queue)

| Item | Detail |
|------|--------|
| **Stands for** | Dead Letter Queue |
| **Used for** | Webhook processing failed 3× → stored in Redis for retry |
| **Env** | `WEBHOOK_DLQ_REDIS_KEY`, `WEBHOOK_DLQ_MAX_ATTEMPTS=3`, beat every **300s** |
| **Code** | `app/worker/dlq.py`, Celery beat + `webhook.process` task |

**Test:** `pytest tests/test_webhook_dlq.py -q`  
**Needs:** Celery worker + Redis running.

---

### Read caches (Chatwoot API — different TTLs)

| Cache | TTL | Env | Purpose |
|-------|-----|-----|---------|
| Ticket | **60s** | `TICKET_READ_CACHE_TTL_SECONDS` | Fewer `get_ticket` calls |
| Contact | **24h** | `CONTACT_READ_CACHE_TTL_SECONDS=86400` | Stable contact lookups |

**Code:** `app/providers/ticketing/caching_adapter.py`  
**Test:** `pytest tests/test_ticketing_read_cache.py -q`

---

### Tiered authorization (agent tools)

| Tier | Meaning in V1 plan |
|------|-------------------|
| **1** | Read-only auto (or block fixes) |
| **2** | Fix on high confidence / soft confirm |
| **3** | Always escalate to human |

**Used for:** MCP tool policy + mapping status (`max_agent_tier` from SLA/payment/coverage).  
**Code:** `app/services/mapping/evaluator.py`, `docs/DECISIONS.md` (D-16 area).  
**Test:** `pytest tests/test_customer_mapping.py -q` (tier caps per status).  
**Note:** Full tier enforcement in agent loop is Phase 2+; mapping already computes tier.

---

### Customer / branch mapping (feeds SLA)

| Item | Detail |
|------|--------|
| **Used for** | Resolve `butterpos_user_id` → branch → restaurant → `plan_type` → SLA row |
| **Code** | `app/services/mapping/`, `app/repositories/customer_mapping_repository.py` |
| **Seed** | `python scripts/seed_data.py`, `python scripts/validate_seed.py` |

Same family as SLA — easy to confuse with Chatwoot escalation.

---

### PII on inbound webhooks

| Item | Detail |
|------|--------|
| **Used for** | Mask `message_body` from Chatwoot **before** cache/agent (same 24h token store) |
| **Code** | `app/services/inbound_pii_service.py` |

Runs in webhook processor, not only on chat `POST /messages`.

---

### MCP + OpenRouter (not SLA/HMAC)

| Item | Detail |
|------|--------|
| **MCP** | Tool server (menu, printer, sales) — `MCP_SERVER_URL` |
| **OpenRouter** | Paid LLM gateway — `OPENROUTER_API_KEY` |
| **PII** | Mandatory mask **before** every OpenRouter call |

**Test:** `curl http://127.0.0.1:8000/api/v1/chat/health` → `mcp_tools`, `openrouter_configured`.

---

### Cheat sheet: multiple “86400” values

| Env var | 86400 means |
|---------|-------------|
| `PII_TOKEN_TTL_SECONDS` | PII unmask map (24h) |
| `CONTACT_READ_CACHE_TTL_SECONDS` | Contact cache (24h) |
| `REQUEST_DEDUP_TTL_SECONDS` | Create-ticket dedup result (24h) |
| `WEBHOOK_HOT_DEDUP_TTL_SECONDS` | Webhook hot dedup (24h) |
| `RATE_LIMIT_RESTAURANT_WINDOW_SECONDS` | Restaurant limit **window** (24h), not a cache TTL |

Do not mix them up — each controls a **different** Redis key prefix.

---

## Related docs

- `docs/AUTH.md` — JWT, HMAC, PII in depth  
- `docs/WEBHOOKS.md` — webhook lifecycle  
- `docs/DATA_MODELS.md` — `sla_config` schema  
- `docs/ENVIRONMENT.md` — all env vars  
- `docs/TROUBLESHOOTING.md` — common failures  

## One-line smoke (core + related)

```bash
pytest tests/test_customer_mapping.py tests/test_chatwoot_webhooks.py tests/test_pii_masker.py \
  tests/test_auth.py tests/test_rate_limits.py tests/test_webhook_idempotency.py \
  tests/test_request_dedup.py tests/test_ticketing_read_cache.py -q
python scripts/validate_seed.py
```
