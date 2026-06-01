# Step 0.2 — LLM Evaluation

**Goal:** Pick primary + fallback model using real ButterPOS support queries, scored against D-5 bars.

## Prerequisites

- `OPENAI_API_KEY` in repo-root `.env` (D-8: OpenAI only today)
- Python 3.11+ with `openai` and `python-dotenv`

```bash
.venv/bin/pip install openai python-dotenv
cd spikes/0.2_llm_eval
../../.venv/bin/python run_eval.py
```

## Dataset

`dataset/support_queries.json` — 50 queries:

| Bucket | Count |
|--------|-------|
| English | 15 |
| Roman Urdu | 15 |
| Code-switched | 10 |
| Short/vague | 5 |
| Multi-step | 5 |

## Candidates (D-8)

| Provider | Models | Status |
|----------|--------|--------|
| OpenAI | `gpt-4o`, `gpt-4o-mini` | Tested when key available |
| Google Gemini | — | Deferred — test when key available |
| Anthropic Claude | — | Deferred — test when key available |

## Scoring (D-5)

| Metric | Target |
|--------|--------|
| Roman Urdu acceptable | ≥75% (judge score ≥4/5 on Urdu + code-switched queries) |
| Latency | p95 <8s, ≥90% of queries <8s |
| Cost | Tracked as $/1K tokens |

Roman Urdu quality is judged by a **fixed** model (`gpt-4o-mini` by default) to avoid circular self-scoring.

## LLMProvider interface

Spike prototype in `providers/` — same pattern as production `LLMProvider` (D-3). Only the adapter imports `openai`; the eval runner talks to the interface.

## Output

Results written to `results/eval_report_*.json` including per-query responses, scorecards, and primary/fallback selection.
