# ButterPOS AI Support Agent — Middleware

Autonomous support agent middleware for ButterPOS: Chatwoot ticketing, LLM reasoning (via `LLMProvider`), MCP tool calling, PII masking.

**Status:** Phase 0 (Discovery & Spikes). Production middleware starts Phase 1.

## Quick start (local infra)

```bash
# 1. Copy env template and fill secrets (never commit .env)
cp .env.example .env

# 2. Start Postgres 15 + Redis 7
docker compose up -d

# 3. Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# 4. Verify infrastructure
python scripts/check_infra.py
pytest tests/ -v
```

## Phase 0 spikes

| Step | Directory |
|------|-----------|
| 0.1 Chat surface | `spikes/0.1_chat_surface/` |
| 0.2 LLM eval | `spikes/0.2_llm_eval/` |
| 0.3 KB audit | `spikes/0.3_kb_audit/` |
| 0.4 Assumptions | `spikes/0.4_assumption_validation/` |

## Docs

See [`docs/EXECUTION_PLAN.md`](docs/EXECUTION_PLAN.md) and [`docs/PROGRESS.md`](docs/PROGRESS.md).

## CI

GitHub Actions (`.github/workflows/ci.yml`): **ruff lint** → **pytest** → **infra connectivity check** on push/PR to `main` and `staging`.
