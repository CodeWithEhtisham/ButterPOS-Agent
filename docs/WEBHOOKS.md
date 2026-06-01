# Webhooks

Inbound webhook handling for the ticketing platform (Chatwoot).

---

## Inbound lifecycle

1. Chatwoot POSTs JSON to middleware webhook URL (`POST /api/v1/webhooks/chatwoot` — Phase 1).
2. `ChatwootAdapter.verify_webhook()` validates HMAC signature.
3. `ChatwootAdapter.parse_webhook()` maps payload → `StandardEvent`.
4. Idempotency check (unique key + payload hash) — skip duplicates.
5. Process event (queue agent loop, invalidate cache).
6. Return `200 OK` quickly; failures go to DLQ (Phase 1).

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

<!-- TBD Phase 1: ChatwootAdapter.verify_webhook() implementation. -->

- Header: `X-Chatwoot-Signature` (HMAC-SHA256 of raw body)
- Secret: `CHATWOOT_WEBHOOK_SECRET` env var (set when registering webhook in Chatwoot)
- Reject with `401` if signature invalid; log and do not process

---

## Idempotency

<!-- TBD Phase 1: webhook_event table + Redis dedup. -->

- Unique key: `{event}:{message_id}` or `{event}:{conversation_id}:{updated_at}`
- Payload hash: SHA-256 of raw body stored for audit
- Duplicate events: ack `200`, skip processing

---

## DLQ

<!-- TBD Phase 1: Celery retry task. -->

- Failed processing → Redis DLQ
- Retry every 5 min, max 3 attempts
- Alert after 3 failures

---

## Polling fallback

<!-- TBD Phase 1: Celery beat task. -->

- Query Chatwoot every 10 min for conversations updated since last sync
- Reconcile with local ticket cache
- Defense in depth when webhooks are dropped
