# Step 0.2 — LLM Evaluation

**Goal:** Pick primary + fallback model using real ButterPOS support queries, scored against D-5 bars.

## Prerequisites

- `OPENROUTER_API_KEY` in repo-root `.env` (D-11: unified gateway for all vendors)
- Python 3.11+ with `openai` (OpenRouter-compatible client) and `python-dotenv`

```bash
.venv/bin/pip install openai python-dotenv
cd spikes/0.2_llm_eval
../../.venv/bin/python run_eval.py
```

## Switching models

Pass any [OpenRouter model slug](https://openrouter.ai/models) via `--models`:

```bash
# OpenAI models
python run_eval.py --models openai/gpt-4o openai/gpt-4o-mini

# Cross-vendor comparison (one API key)
python run_eval.py --models openai/gpt-4o anthropic/claude-3.5-sonnet google/gemini-2.0-flash-001
```

Set defaults in `.env`: `LLM_PRIMARY_MODEL`, `LLM_FALLBACK_MODEL`, `LLM_JUDGE_MODEL`.

## Dataset

`dataset/support_queries.json` — 50 queries:

| Bucket | Count |
|--------|-------|
| English | 15 |
| Roman Urdu | 15 |
| Code-switched | 10 |
| Short/vague | 5 |
| Multi-step | 5 |

## Candidates (default)

| OpenRouter slug | Vendor |
|-----------------|--------|
| `openai/gpt-4o` | OpenAI |
| `openai/gpt-4o-mini` | OpenAI |

Any supported slug can be added via `--models` — no code changes.

## Scoring (D-5)

| Metric | Target |
|--------|--------|
| Roman Urdu acceptable | ≥75% (judge score ≥4/5 on Urdu + code-switched queries) |
| Latency | p95 <8s, ≥90% of queries <8s |
| Cost | Tracked as $/1K tokens |

Roman Urdu quality is judged by a **fixed** model (`openai/gpt-4o-mini` by default) to avoid circular self-scoring.

## LLMProvider interface

Spike prototype in `providers/` — same pattern as production `LLMProvider` (D-3). Only `OpenRouterProvider` imports the HTTP client; the eval runner talks to the interface.

## Output

Results written to `results/eval_report_*.json` including per-query responses, scorecards, and primary/fallback selection.
