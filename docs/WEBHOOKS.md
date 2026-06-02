# Webhooks

Inbound webhook handling for the ticketing platform (Chatwoot).

---

## Inbound lifecycle

1. Chatwoot POSTs JSON to `POST /api/v1/webhooks/chatwoot` (**Task 1.4.1** — live).
2. `WebhookService` reads **raw body bytes** and calls `ChatwootAdapter.verify_webhook()`.
3. `ChatwootAdapter.parse_webhook()` maps payload → `StandardEvent`.
4. Endpoint returns `200` with `status: accepted`, `status: duplicate`, or `status: rate_limited` (**Task 1.4.2** + **1.5.2**).
5. Idempotency row persisted in `webhook_event_log` (`received` on first delivery; replays skip insert).
6. Incoming customer messages checked against Redis sliding-window rate limits (**Task 1.5.2**) before Celery enqueue.
7. Process event via Celery `webhook.process` (**Task 1.4.3** — live stub processor).
8. Failures → Redis DLQ + beat retry (**Task 1.4.3**).

---

## Chatwoot payload shape

Chatwoot sends **object-specific payloads** — always branch on the `event` field before parsing.

### Subscribed events (V1)

| Event | When fired |
|-------|------------|
| `message_created` | New incoming or outgoing message |
| `message_updated` | Message edited or CSAT submitted |
| `conversation_status_changed` | open / resolved / pending |
| `conversation_updated` | Conversation attributes changed |
| `webwidget_triggered` | Widget opened (web widget inboxes only) |

### `message_created` (primary event for middleware)

Top-level object is **message-shaped**; conversation is nested under `conversation`.

```json
{
  "event": "message_created",
  "id": 12345,
  "content": "Printer offline hai",
  "content_type": "text",
  "content_attributes": {},
  "message_type": "incoming",
  "created_at": "2026-03-04T10:30:00Z",
  "private": false,
  "source_id": "ext-msg-123",
  "sender": {
    "id": 101,
    "name": "Branch User",
    "type": "contact"
  },
  "conversation": {
    "id": 5678,
    "inbox_id": 42,
    "status": "open"
  },
  "account": { "id": 1 },
  "inbox": { "id": 42, "name": "ButterPOS API" }
}
```

### Interactive reply (`input_select` / `cards` postback)

When a user selects a quick reply or card button, `message_created` fires with:

- `message_type`: `incoming`
- `content_type`: `text` (the selected value) or template type
- `content_attributes.submitted_values` or `content`: the chosen option value/payload

Middleware maps this to playbook step continuation.

### CSAT response (API channel)

CSAT ratings submitted via public message update:

```json
{
  "submitted_values": {
    "csat_survey_response": {
      "rating": 5,
      "feedback_message": "Theek chal raha hai"
    }
  }
}
```

Alternative: redirect tablet to Chatwoot-hosted survey at `/survey/responses/{conversation_uuid}`.

**Source:** [Chatwoot webhooks user guide](https://chatwoot.help/hc/user-guide/articles/1677693021-how-to-use-webhooks), Step 0.1 spike.

---

## HMAC verification

Implemented in `app/providers/ticketing/chatwoot/webhooks.py` → `ChatwootAdapter.verify_webhook()`.

| Item | Detail |
|------|--------|
| Headers | `X-Chatwoot-Signature`, `X-Chatwoot-Timestamp` |
| Algorithm | `sha256=HMAC-SHA256(secret, "{timestamp}.{raw_body}")` |
| Secret | `CHATWOOT_WEBHOOK_SECRET` — returned once when webhook is registered |
| Replay window | `CHATWOOT_WEBHOOK_MAX_AGE_SECONDS` (default `300`) |
| Comparison | `hmac.compare_digest` (constant-time) |

**Important:** Verify against the **raw request body bytes** — do not re-serialize JSON.

Reject with `401` if signature invalid or timestamp too old; log and do not process.

### Webhook registration (Task 1.3.7)

Register via Chatwoot UI (Settings → Integrations → Webhooks) **or** adapter helper:

```python
adapter = ChatwootAdapter(settings)
result = await adapter.register_webhook("https://your-host/api/v1/webhooks/chatwoot")
# Save result["secret"] → CHATWOOT_WEBHOOK_SECRET in .env
```

API: `POST /api/v1/accounts/{account_id}/webhooks` with V1 subscriptions (`message_created`, `conversation_status_changed`, etc.).

Local dev may require HTTPS or ngrok — Chatwoot rejects plain HTTP URLs in production mode.

---

## Idempotency

Persisted in Postgres table `webhook_event_log` (Task 1.2.5). **Redis hot dedup** (Task 1.5.3) checks `idempotency_key` before Postgres on replays within TTL.

| Field | Purpose |
|-------|---------|
| `idempotency_key` | Unique — `{event}:{message_id}` or `{event}:{conversation_id}:{updated_at}` |
| `payload_hash` | SHA-256 hex (64 chars) of raw request body for audit |
| `status` | `received`, `processed`, `duplicate`, `failed` |

**Flow (Task 1.4.2 — implemented):**

1. Compute `idempotency_key` (from adapter) and `payload_hash` = SHA-256 hex of raw body.
2. Insert row with `status=received`; on unique violation → return `200` with `status=duplicate`, skip processing.
3. On success → return `200` with `status=accepted` (processing deferred to agent loop).
4. On processing failure (later) → set `status=failed`, `error_message`; push to Redis DLQ for retry.

Duplicate events: ack `200`, skip processing.

---

## Rate limiting

**Task 1.5.2** — sliding-window quotas on **incoming customer** `message_created` events only (after idempotency insert, before Celery dispatch).

| Scope | Default limit | Window | Redis key prefix | Key source |
|-------|---------------|--------|------------------|------------|
| User | 20 messages | 1 hour | `ratelimit:user:` | Chatwoot contact id (`sender_provider_contact_id`) until Task 1.6 maps ButterPOS user ids |
| Restaurant | 100 messages | 24 hours | `ratelimit:restaurant:` | `conversation.custom_attributes.restaurant_id` or `butterpos_restaurant_id`; skipped if absent |

**Flow:**

1. New webhook passes idempotency → rate limiter checks user and (when present) restaurant keys.
2. Within quota → Celery `webhook.process` enqueued; HTTP `200` with `status: accepted`.
3. Over quota → audit row marked `failed` with error message; HTTP **`200`** with `status: rate_limited` (no Celery enqueue — avoids Chatwoot retry amplification).
4. Duplicate replays → no rate-limit consumption (check runs only when insert status is `received`).

Implementation: `app/core/rate_limit/sliding_window.py`, `app/core/rate_limit/inbound_message_limits.py`, wired in `WebhookService.receive_chatwoot()`.

Env vars: see `ENVIRONMENT.md` § Inbound message rate limits.

---

## Request deduplication

**Task 1.5.3** — two Redis-backed dedup layers:

### Ticket creation (double-tap protection)

When the tablet widget calls `create_ticket()` with a client id in metadata:

| Metadata key | Purpose |
|--------------|---------|
| `client_request_id` | Preferred — UUID from widget per tap |
| `source_id` | Chatwoot source id (also used by adapter) |
| `idempotency_key` | Generic fallback |

If none are set, every call creates a new conversation (no dedup). Replays within `REQUEST_DEDUP_TTL_SECONDS` return the cached `StandardTicket` without a second Chatwoot API call.

Factory chain: `ChatwootAdapter` → `DedupingTicketingProvider` → `CachingTicketingProvider`.

### Webhook hot path

Before Postgres insert, `WebhookHotDedupStore` checks Redis for a recent `idempotency_key`. On hit → HTTP `200` + `status: duplicate` without touching Postgres. On first accept → key stored in Redis after Postgres `received`.

---

## DLQ

**Task 1.4.3** — failed processing → Redis sorted set → Celery beat retries.

| Item | Detail |
|------|--------|
| Redis key | `WEBHOOK_DLQ_REDIS_KEY` (default `webhook:dlq:pending`) |
| Max attempts | `WEBHOOK_DLQ_MAX_ATTEMPTS` (default `3`) |
| Retry interval | `WEBHOOK_DLQ_RETRY_INTERVAL_SECONDS` (default `300` = 5 min) |
| Celery tasks | `webhook.process`, `webhook.retry_dlq` (beat) |
| Alert | Structured log `alert_type=webhook_dlq_exhausted` after 3 failures |

**Flow:**

1. New webhook (`status=received`) → Celery `webhook.process` dispatched (HTTP returns `200` immediately).
2. Processor succeeds → `webhook_event_log.status=processed`, `processed_at` set.
3. Processor fails → `status=failed`, `error_message` set, entry pushed to Redis DLQ with `next_retry_at`.
4. Celery beat (`webhook.retry_dlq`) every 5 min drains ready DLQ entries and re-dispatches `webhook.process`.
5. After 3 total attempts → no further DLQ enqueue; `webhook_dlq_exhausted` error log for ops monitoring.

If Celery broker is unreachable at dispatch time, the HTTP handler pushes directly to DLQ (same payload shape).

**Run workers locally:**

```bash
celery -A app.worker.celery_app worker -l info
celery -A app.worker.celery_app beat -l info
```

Requires `REDIS_URL` (broker + DLQ).

---

## Polling fallback

**Task 1.4.4** — Celery beat reconciles Chatwoot ↔ Postgres `ticket_cache` when webhooks are dropped.

| Item | Detail |
|------|--------|
| Beat task | `ticket.poll_reconcile` every `WEBHOOK_POLLING_INTERVAL_SECONDS` (default `600` = 10 min) |
| Cursor | Redis key `WEBHOOK_POLLING_CURSOR_REDIS_KEY` — last successful poll timestamp |
| First run | Looks back `WEBHOOK_POLLING_INITIAL_LOOKBACK_SECONDS` (default `900` = 15 min) if no cursor |
| Platform API | `TicketingProvider.list_tickets_updated_since()` → Chatwoot `POST /conversations/filter` |
| Local mirror | Upsert into `ticket_cache` — create, update, or touch `synced_at` |

Defense in depth alongside webhooks + DLQ: missed webhook events are eventually reflected in the durable mirror within one poll interval.
