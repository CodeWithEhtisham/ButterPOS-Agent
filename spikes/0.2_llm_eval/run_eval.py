#!/usr/bin/env python3
"""
Step 0.2 — LLM Evaluation runner.

Sends every query in dataset/support_queries.json through each candidate model
via the LLMProvider interface, scores against D-5 bars, and picks primary + fallback.

Required env: OPENROUTER_API_KEY

Usage:
  cd spikes/0.2_llm_eval
  python run_eval.py
  python run_eval.py --models openai/gpt-4o openai/gpt-4o-mini --judge-model openai/gpt-4o-mini
  python run_eval.py --models anthropic/claude-3.5-sonnet google/gemini-2.0-flash-001
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Allow imports from providers/ when run from this directory
_SPIKE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SPIKE_DIR))

from providers.base import LLMProvider, LLMRequest  # noqa: E402
from providers.openrouter_provider import OpenRouterProvider  # noqa: E402

RESULTS_DIR = _SPIKE_DIR / "results"
DATASET_PATH = _SPIKE_DIR / "dataset" / "support_queries.json"

LATENCY_TARGET_MS = 8000  # D-5
ROMAN_URDU_TARGET_PCT = 75.0  # D-5
JUDGE_ACCEPT_THRESHOLD = 4  # score >= 4 on 1-5 scale = acceptable

URDU_CATEGORIES = frozenset({"roman_urdu", "code_switched"})


@dataclass
class QueryResult:
    query_id: str
    category: str
    topic: str
    query: str
    response: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    judge_score: int | None = None
    judge_acceptable: bool | None = None
    judge_reason: str | None = None


@dataclass
class ModelScorecard:
    provider: str
    model: str
    query_count: int
    latency_mean_ms: float
    latency_p95_ms: float
    latency_under_8s_pct: float
    total_tokens: int
    total_cost_usd: float
    cost_per_1k_tokens_usd: float
    roman_urdu_scored: int
    roman_urdu_acceptable_pct: float
    d5_latency_pass: bool
    d5_roman_urdu_pass: bool
    d5_overall_pass: bool
    results: list[QueryResult] = field(default_factory=list)


@dataclass
class EvalReport:
    timestamp: str
    candidates_tested: list[str]
    candidates_deferred: list[str]
    judge_model: str
    scorecards: list[ModelScorecard]
    primary: str | None
    fallback: str | None
    selection_rationale: str
    error: str | None = None


def load_dataset() -> dict[str, Any]:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def build_provider(name: str, api_key: str) -> LLMProvider:
    if name == "openrouter":
        return OpenRouterProvider(api_key=api_key)
    raise ValueError(f"Unknown provider: {name}")


async def judge_response(
    provider: LLMProvider,
    judge_model: str,
    query: str,
    response: str,
    category: str,
) -> tuple[int, bool, str]:
    """Fixed judge model scores Roman Urdu / code-switched response quality."""
    prompt = f"""You are evaluating ButterPOS support bot responses for Roman Urdu quality.

User category: {category}
User query: {query}

Assistant response:
{response}

Score 1-5:
5 = Excellent — correct language match, helpful, actionable, natural Roman Urdu or appropriate bilingual
4 = Acceptable — minor issues but usable by restaurant staff
3 = Borderline — partially helpful or awkward language
2 = Poor — wrong language or mostly unhelpful
1 = Unacceptable — wrong language, nonsense, or harmful

Reply as JSON only: {{"score": N, "acceptable": true/false, "reason": "one sentence"}}"""

    result = await provider.complete(
        LLMRequest(
            messages=[{"role": "user", "content": prompt}],
            model=judge_model,
            temperature=0.0,
            max_tokens=120,
        )
    )
    try:
        parsed = json.loads(result.content.strip().removeprefix("```json").removesuffix("```"))
        score = int(parsed["score"])
        acceptable = bool(parsed.get("acceptable", score >= JUDGE_ACCEPT_THRESHOLD))
        reason = str(parsed.get("reason", ""))
    except (json.JSONDecodeError, KeyError, ValueError):
        score = 3
        acceptable = False
        reason = "Judge parse failed"
    return score, acceptable, reason


async def evaluate_model(
    provider: LLMProvider,
    model: str,
    dataset: dict[str, Any],
    judge_model: str,
    *,
    judge_urdu: bool = True,
) -> ModelScorecard:
    system_prompt = dataset["system_prompt"]
    queries = dataset["queries"]
    results: list[QueryResult] = []

    for q in queries:
        req = LLMRequest(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": q["text"]},
            ],
            model=model,
            temperature=0.3,
            max_tokens=400,
        )
        resp = await provider.complete(req)

        judge_score: int | None = None
        judge_acceptable: bool | None = None
        judge_reason: str | None = None

        if judge_urdu and q["category"] in URDU_CATEGORIES:
            judge_score, judge_acceptable, judge_reason = await judge_response(
                provider, judge_model, q["text"], resp.content, q["category"]
            )
            await asyncio.sleep(0.2)  # gentle rate limit between judge calls

        results.append(
            QueryResult(
                query_id=q["id"],
                category=q["category"],
                topic=q["topic"],
                query=q["text"],
                response=resp.content,
                latency_ms=resp.latency_ms,
                prompt_tokens=resp.prompt_tokens,
                completion_tokens=resp.completion_tokens,
                total_tokens=resp.total_tokens,
                cost_usd=resp.cost_usd,
                judge_score=judge_score,
                judge_acceptable=judge_acceptable,
                judge_reason=judge_reason,
            )
        )
        await asyncio.sleep(0.1)

    latencies = [r.latency_ms for r in results]
    lat_sorted = sorted(latencies)
    p95_idx = max(0, int(len(lat_sorted) * 0.95) - 1)
    latency_p95 = lat_sorted[p95_idx] if lat_sorted else 0.0
    under_8s = sum(1 for l in latencies if l < LATENCY_TARGET_MS) / len(latencies) * 100

    total_tokens = sum(r.total_tokens for r in results)
    total_cost = sum(r.cost_usd for r in results)
    cost_per_1k = (total_cost / total_tokens * 1000) if total_tokens else 0.0

    urdu_results = [r for r in results if r.category in URDU_CATEGORIES and r.judge_acceptable is not None]
    urdu_acceptable = sum(1 for r in urdu_results if r.judge_acceptable)
    urdu_pct = (urdu_acceptable / len(urdu_results) * 100) if urdu_results else 0.0

    d5_latency = latency_p95 < LATENCY_TARGET_MS and under_8s >= 90.0
    d5_urdu = urdu_pct >= ROMAN_URDU_TARGET_PCT
    d5_overall = d5_latency and d5_urdu

    return ModelScorecard(
        provider=provider.provider_name,
        model=model,
        query_count=len(results),
        latency_mean_ms=round(statistics.mean(latencies), 2) if latencies else 0.0,
        latency_p95_ms=round(latency_p95, 2),
        latency_under_8s_pct=round(under_8s, 1),
        total_tokens=total_tokens,
        total_cost_usd=round(total_cost, 4),
        cost_per_1k_tokens_usd=round(cost_per_1k, 4),
        roman_urdu_scored=len(urdu_results),
        roman_urdu_acceptable_pct=round(urdu_pct, 1),
        d5_latency_pass=d5_latency,
        d5_roman_urdu_pass=d5_urdu,
        d5_overall_pass=d5_overall,
        results=results,
    )


def select_primary_fallback(scorecards: list[ModelScorecard]) -> tuple[str | None, str | None, str]:
    passing = [s for s in scorecards if s.d5_overall_pass]
    if not passing:
        # Pick best Roman Urdu if none fully pass
        by_urdu = sorted(scorecards, key=lambda s: (-s.roman_urdu_acceptable_pct, s.latency_p95_ms))
        if len(by_urdu) >= 2:
            return (
                by_urdu[0].model,
                by_urdu[1].model,
                "No model met all D-5 bars; primary=f best Roman Urdu score, fallback=second.",
            )
        if by_urdu:
            return by_urdu[0].model, None, "Only one candidate; D-5 bars not fully met."
        return None, None, "No candidates evaluated."

    # Primary: best Roman Urdu among passing; tie-break lower latency
    passing.sort(key=lambda s: (-s.roman_urdu_acceptable_pct, s.latency_mean_ms))
    primary = passing[0].model

    # Fallback: cheapest passing model that isn't primary
    others = [s for s in passing if s.model != primary]
    if others:
        others.sort(key=lambda s: (s.cost_per_1k_tokens_usd, s.latency_mean_ms))
        fallback = others[0].model
        rationale = (
            f"Primary={primary}: highest Roman Urdu acceptability ({passing[0].roman_urdu_acceptable_pct}%) "
            f"with D-5 pass. Fallback={fallback}: lower cost (${others[0].cost_per_1k_tokens_usd}/1K tokens) "
            f"while meeting D-5 bars."
        )
    else:
        fallback = None
        rationale = f"Primary={primary} only passing candidate."

    return primary, fallback, rationale


def write_report(report: EvalReport) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = RESULTS_DIR / f"eval_report_{stamp}.json"
    path.write_text(json.dumps(asdict(report), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def print_summary(report: EvalReport) -> None:
    print("\n=== Step 0.2 LLM Evaluation ===\n")
    if report.error:
        print(f"ERROR: {report.error}\n")
        return

    print(f"Judge model: {report.judge_model}")
    print(f"Deferred: {', '.join(report.candidates_deferred) or 'none'}\n")

    print(f"{'Model':<16} {'Urdu%':>6} {'p95 ms':>8} {'<8s%':>6} {'$/1K tok':>9} {'D-5':>5}")
    print("-" * 58)
    for s in report.scorecards:
        d5 = "PASS" if s.d5_overall_pass else "FAIL"
        print(
            f"{s.model:<16} {s.roman_urdu_acceptable_pct:>5.1f}% "
            f"{s.latency_p95_ms:>8.0f} {s.latency_under_8s_pct:>5.1f}% "
            f"{s.cost_per_1k_tokens_usd:>9.4f} {d5:>5}"
        )

    print(f"\nPrimary:  {report.primary}")
    print(f"Fallback: {report.fallback}")
    print(f"Rationale: {report.selection_rationale}\n")


async def run(args: argparse.Namespace) -> EvalReport:
    load_dotenv(_SPIKE_DIR.parents[1] / ".env")
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("Missing OPENROUTER_API_KEY in .env")

    dataset = load_dataset()
    provider = build_provider("openrouter", api_key)

    scorecards: list[ModelScorecard] = []
    for model in args.models:
        print(f"Evaluating {model} ({len(dataset['queries'])} queries)...")
        t0 = time.perf_counter()
        sc = await evaluate_model(
            provider, model, dataset, args.judge_model, judge_urdu=not args.skip_judge
        )
        print(f"  Done in {time.perf_counter() - t0:.1f}s — Urdu {sc.roman_urdu_acceptable_pct}% p95 {sc.latency_p95_ms}ms")
        scorecards.append(sc)

    primary, fallback, rationale = select_primary_fallback(scorecards)

    return EvalReport(
        timestamp=datetime.now(UTC).isoformat(),
        candidates_tested=list(args.models),
        candidates_deferred=[],  # any OpenRouter slug can be passed via --models
        judge_model=args.judge_model,
        scorecards=scorecards,
        primary=primary,
        fallback=fallback,
        selection_rationale=rationale,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="ButterPOS LLM eval — Step 0.2")
    parser.add_argument(
        "--models",
        nargs="+",
        default=["openai/gpt-4o", "openai/gpt-4o-mini"],
        help="OpenRouter model slugs to evaluate (e.g. openai/gpt-4o, anthropic/claude-3.5-sonnet)",
    )
    parser.add_argument(
        "--judge-model",
        default="openai/gpt-4o-mini",
        help="Fixed judge model slug for Roman Urdu scoring",
    )
    parser.add_argument("--skip-judge", action="store_true", help="Skip Roman Urdu judge (latency/cost only)")
    args = parser.parse_args()

    report = EvalReport(
        timestamp=datetime.now(UTC).isoformat(),
        candidates_tested=[],
        candidates_deferred=[],
        judge_model=args.judge_model,
        scorecards=[],
        primary=None,
        fallback=None,
        selection_rationale="",
    )

    try:
        report = asyncio.run(run(args))
    except SystemExit as exc:
        report.error = str(exc)
        print(exc, file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 — spike top-level
        report.error = str(exc)
        print(report.error, file=sys.stderr)

    path = write_report(report)
    print_summary(report)
    print(f"Report: {path}")
    return 0 if report.error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
