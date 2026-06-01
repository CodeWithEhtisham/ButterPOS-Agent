#!/usr/bin/env python3
"""
Step 0.6 — MCP client validation spike.

1. Connects to stub MCP server (stdio) — placeholder until backend teammate ships production server.
2. Direct tool probe (no LLM) — all 4 tools must succeed.
3. LLM + MCP agent loop via LLMProvider — tests tool portability across models.

Required for LLM tests: OPENROUTER_API_KEY in .env
Tests tool portability across OpenRouter model slugs (same MCP client, swap model = config only).

Usage:
  cd spikes/0.6_mcp_validation
  python run_validation.py
  python run_validation.py --models openai/gpt-4o anthropic/claude-3.5-sonnet
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

_SPIKE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SPIKE_DIR))
sys.path.insert(0, str(_SPIKE_DIR.parent / "0.2_llm_eval"))

from client.agent_loop import AgentLoopResult, run_agent_loop  # noqa: E402
from client.mcp_client import MCPClient  # noqa: E402
from providers.openrouter_provider import OpenRouterProvider  # noqa: E402

RESULTS_DIR = _SPIKE_DIR / "results"
EXPECTED_TOOLS = frozenset(
    {"get_system_info", "check_printer", "get_sales", "add_menu_item"}
)

TEST_QUERIES = [
    "Printer offline hai branch 101 pe — check karo aur batao kya karna hai.",
    "Branch 101 ki aaj ki sales kitni hain?",
]


@dataclass
class ValidationReport:
    timestamp: str
    server: str
    transport: str
    tools_discovered: list[str]
    direct_probe_pass: bool
    direct_probe_results: list[dict]
    llm_tests: list[dict] = field(default_factory=list)
    llm_portability_pass: bool | None = None
    llm_skipped_reason: str | None = None
    error: str | None = None


async def run_direct_probe(mcp: MCPClient) -> tuple[bool, list[dict]]:
    tools = await mcp.connect_and_list_tools()
    names = {t.name for t in tools}
    missing = EXPECTED_TOOLS - names
    if missing:
        return False, [{"error": f"Missing tools: {sorted(missing)}"}]

    results = await mcp.run_direct_probe()
    ok = all(not r.is_error for r in results)
    return ok, [
        {
            "tool_name": r.tool_name,
            "arguments": r.arguments,
            "content": r.content[:300],
            "is_error": r.is_error,
        }
        for r in results
    ]


async def run_llm_tests(
    mcp: MCPClient,
    models: list[str],
) -> tuple[list[dict], bool | None, str | None]:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return [], None, "OPENROUTER_API_KEY not set — LLM portability test skipped"

    await mcp.connect_and_list_tools()
    llm = OpenRouterProvider(api_key=api_key)
    records: list[dict] = []
    all_pass = True

    for model in models:
        for query in TEST_QUERIES:
            loop_result: AgentLoopResult = await run_agent_loop(
                llm, mcp, model=model, user_query=query
            )
            tool_names = [tc.tool_name for tc in loop_result.tool_calls]
            success = bool(loop_result.tool_calls) and all(
                tc.success for tc in loop_result.tool_calls
            )
            if not success:
                all_pass = False
            records.append(
                {
                    "model": model,
                    "query": query,
                    "tools_called": tool_names,
                    "success": success,
                    "error": loop_result.error,
                    "final_content_preview": (loop_result.final_content or "")[:200],
                }
            )

    return records, all_pass, None


async def main_async(args: argparse.Namespace) -> ValidationReport:
    stub_path = Path(args.stub_server)
    mcp = MCPClient.for_stub(stub_path)

    report = ValidationReport(
        timestamp=datetime.now(UTC).isoformat(),
        server="butterpos_stub_mcp.py (Phase 0 placeholder)",
        transport="stdio",
        tools_discovered=[],
        direct_probe_pass=False,
        direct_probe_results=[],
    )

    try:
        tools = await mcp.connect_and_list_tools()
        report.tools_discovered = [t.name for t in tools]

        probe_ok, probe_results = await run_direct_probe(mcp)
        report.direct_probe_pass = probe_ok
        report.direct_probe_results = probe_results

        llm_records, llm_pass, skip_reason = await run_llm_tests(mcp, args.models)
        report.llm_tests = llm_records
        report.llm_portability_pass = llm_pass
        report.llm_skipped_reason = skip_reason

    except Exception as exc:  # noqa: BLE001 — spike top-level
        report.error = str(exc)

    return report


def print_summary(report: ValidationReport) -> None:
    print("\n=== Step 0.6 MCP Client Validation ===\n")
    print(f"Server: {report.server} ({report.transport})")

    if report.error:
        print(f"\nERROR: {report.error}\n")
        return

    print(f"Tools discovered: {', '.join(report.tools_discovered)}")
    print(f"Direct probe:   {'PASS' if report.direct_probe_pass else 'FAIL'}")

    if report.llm_skipped_reason:
        print(f"LLM tests:      SKIPPED — {report.llm_skipped_reason}")
    elif report.llm_portability_pass is not None:
        status = "PASS" if report.llm_portability_pass else "FAIL"
        print(f"LLM portability ({len(report.llm_tests)} runs): {status}")
        for t in report.llm_tests:
            mark = "OK" if t["success"] else "FAIL"
            print(f"  [{mark}] {t['model']}: {t['tools_called']}")

    print()


def main() -> int:
    load_dotenv(_SPIKE_DIR.parents[1] / ".env")
    parser = argparse.ArgumentParser(description="MCP client validation — Step 0.6")
    parser.add_argument(
        "--stub-server",
        default=str(_SPIKE_DIR / "stub_server" / "butterpos_stub_mcp.py"),
        help="Path to stub MCP server script",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["openai/gpt-4o", "openai/gpt-4o-mini"],
        help="OpenRouter model slugs for portability test",
    )
    args = parser.parse_args()

    report = asyncio.run(main_async(args))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"mcp_validation_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    out.write_text(json.dumps(asdict(report), indent=2, ensure_ascii=False), encoding="utf-8")

    print_summary(report)
    print(f"Report: {out}")

    if report.error or not report.direct_probe_pass:
        return 1
    if report.llm_skipped_reason:
        return 0  # direct probe pass is sufficient when no API key
    return 0 if report.llm_portability_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
