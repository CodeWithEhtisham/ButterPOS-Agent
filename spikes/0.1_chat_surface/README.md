# Step 0.1 — Chat Surface Spike

**Goal:** Prove widget → middleware → Chatwoot supports posting messages, rich UI elements, and acceptable round-trip latency (<5s).

This is a **spike**, not production code. It simulates the middleware posting to Chatwoot via the Application API (the path the real middleware will use per D-2).

## Prerequisites

1. Chatwoot running locally (Docker) — see [Chatwoot Docker docs](https://www.chatwoot.com/docs/self-hosted/deployment/docker)
2. An **API Channel** inbox created in Chatwoot (Settings → Inboxes → Add Inbox → API)
3. API access token (Profile → Access Token)

## Environment

Add to `.env` (never commit real values):

```env
CHATWOOT_BASE_URL=http://localhost:3000
CHATWOOT_API_TOKEN=your_token_here
CHATWOOT_ACCOUNT_ID=1
CHATWOOT_INBOX_ID=1
```

## Run

```bash
pip install httpx python-dotenv
python spikes/0.1_chat_surface/chat_surface_spike.py
python spikes/0.1_chat_surface/chat_surface_spike.py --rounds 5
```

Results are written to `spikes/0.1_chat_surface/results/spike_report_*.json`.

## What it tests

| Phase | Action |
|-------|--------|
| Health | `GET /api` |
| Setup | Create contact + conversation in API inbox |
| Latency | Post text message → read back (N rounds) |
| Capabilities | Probe `text`, `input_select`, `cards`, `form` content types |

## Capability matrix (API research baseline)

See [`capability_matrix.md`](capability_matrix.md) for the static analysis. Live probe results overwrite the "Live spike" column when the harness runs successfully.
