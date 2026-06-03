# Troubleshooting

Known issues, platform quirks, and recurring failures with fixes.

---

## Known issues

| Issue | Status | Notes |
|-------|--------|-------|
| Step 0.1 live spike | **Superseded** | Use `python scripts/validate_chatwoot.py` for live adapter checks (Task 1.8.2) |

---

## Chatwoot quirks

Documented during Step 0.1 (API research + spike).

### Interactive messages require JSON body

When sending `input_select`, `cards`, or `form` messages, `content_attributes` must be a **JSON object**, not a URL-encoded string. Sending it as a string causes `String does not have #dig method` from Chatwoot.

**Fix:** Use `Content-Type: application/json` and pass `content_attributes` as a nested object (see spike harness).

### Object-specific webhook payloads

`message_created` payloads are message-shaped (conversation nested). `conversation_updated` payloads are conversation-shaped (different top-level structure). Always branch on `event` before parsing.

**Fix:** `parse_webhook()` in `ChatwootAdapter` must have per-event parsers, not one generic schema.

### API channel requires `source_id`

Creating a conversation via Application API requires a `source_id` (unique per contact-inbox pair). Middleware must generate and persist this when creating conversations.

**Source:** [Create API channel inbox guide](https://www.chatwoot.com/hc/user-guide/articles/1677839703-how-to-create-an-api-channel-inbox)

### CSAT on API channel

- Outgoing CSAT prompt: use `input_csat` content type (agent API)
- Response collection: PATCH public message with `submitted_values.csat_survey_response`, OR redirect to `/survey/responses/{conversation_uuid}`
- CSAT messages cannot be updated after 14 days

---

## Recurring failures + fixes

<!-- Populated as issues are encountered during Phase 0 spikes and Phase 1 development. -->

| Symptom | Cause | Fix |
|---------|-------|-----|
| Spike exits: missing env vars | `.env` not configured | Add `CHATWOOT_*` vars per `ENVIRONMENT.md` |
| `docker compose` port bind failed | Host ports 5432/6379 already in use | Use `POSTGRES_PORT=15432` `REDIS_PORT=16379` and update URLs in `.env` |
| HTTP 401 from Chatwoot | Invalid or expired API token | Regenerate token in Chatwoot Profile → Access Token |
| HTTP 404 on conversation | Wrong `account_id` or conversation deleted | Verify IDs in Chatwoot dashboard URL |
| Presidio tries to download spaCy on startup | `en_core_web_lg` not installed | Run `python -m spacy download en_core_web_lg` or rely on regex fallback (automatic) |
| PII tokens not unmasking | Redis TTL expired (24h) or wrong `REDIS_URL` | Verify Redis connectivity; tokens are ephemeral by design |
| Webhook stuck in `failed` | Celery worker/beat not running | Start `celery worker` + `celery beat`; check Redis DLQ key |
| `webhook_dlq_exhausted` in logs | Event failed 3 processing attempts | Inspect `webhook_event_log.error_message`; fix root cause; manual replay TBD |
| Celery dispatch failed on ingest | Redis broker down at POST time | Event pushed to DLQ directly; start Redis + beat |
| `ticket_cache` stale vs Chatwoot | Webhook missed; polling not running | Ensure Celery beat + worker running; check poll cursor key in Redis |
| `docker compose` postgres fails: port 5432 in use | System Postgres already bound | Use existing Postgres — set `DATABASE_URL` accordingly — or set `POSTGRES_PORT=15432` |
| `smoke_middleware.py` connect refused | Uvicorn not running | Start `uvicorn app.main:app --port 8000` |
| MCP `create_menu_item` / menu tools: `demo_store.json` missing | POS MCP server expects `demo/pos_mcp/demo_store.json` under repo root | Copy or restore from git: `demo/pos_mcp/demo_store.json`; restart MCP server on `:3001` |
| `system_health` HTTP 503 | Postgres or Redis unreachable | Run `python scripts/check_infra.py`; verify `DATABASE_URL` / `REDIS_URL` |
| `validate_chatwoot.py` FAIL on health | Chatwoot down or bad token | Confirm `CHATWOOT_BASE_URL` reachable; regenerate API token |
| `validate_seed.py` FAIL mapping | Seed not applied or fixture mismatch | Run `seed_data.py` then re-validate; check `tenant_validation_service.py` expectations |
| Human agent reply not in widget | Chatwoot webhooks not reaching middleware | Run `python scripts/register_chatwoot_webhook.py --docker-host` (or without flag if both on localhost); set `CHATWOOT_WEBHOOK_SECRET` + `CHATWOOT_WEBHOOK_CALLBACK_URL` in `.env`; restart uvicorn + Celery. **Workaround:** `GET /chat/sessions/{id}` polls Chatwoot API (2.1.3). If Chatwoot is in Docker, use `host.docker.internal` not `127.0.0.1` for webhook URL |
| Customer message echoed as “Support Agent” right after escalation | Escalation posted `initial_message` to Chatwoot as `outgoing` | Fixed in adapter: `create_ticket` uses `message_type=incoming` for customer text. Start a **new** chat session to retest (old tickets may already have the bad message in Chatwoot) |
| `ModuleNotFoundError: app` running scripts | Wrong cwd | Run from repo root; scripts prepend project root to `sys.path` |
