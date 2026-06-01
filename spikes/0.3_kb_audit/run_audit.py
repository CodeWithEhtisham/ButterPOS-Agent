#!/usr/bin/env python3
"""
Step 0.3 — KB Content Audit: WhatsApp message categorizer + MVP list generator.

Reads a WhatsApp support export, categorizes messages, counts issue frequency,
and outputs a top-30 MVP article CSV.

Categories: billing, printer, crash, login, menu, network, general

Usage:
  python run_audit.py --input path/to/export.json
  python run_audit.py --input path/to/export.csv --authors "Ali,Sara,Team Lead"
  python run_audit.py --input sample_data/sample_messages.json --demo
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

_SPIKE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = _SPIKE_DIR / "results"
TEMPLATES_DIR = _SPIKE_DIR / "templates"

CATEGORIES = ("billing", "printer", "crash", "login", "menu", "network", "general")

# Keyword rules — order matters (first match wins)
CATEGORY_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "printer",
        re.compile(
            r"\b(printer|print|receipt|kot|bluetooth\s*print|thermal|offline\s*print|"
            r"blank\s*ticket|chit|invoice\s*print)\b",
            re.I,
        ),
    ),
    (
        "sync",
        re.compile(
            r"\b(sync|cloud|pending\s*order|upload|download|backup|stuck|"
            r"report\s*total|day\s*end|reconcil)\b",
            re.I,
        ),
    ),
    (
        "login",
        re.compile(
            r"\b(login|log\s*in|pin|password|permission|access|auth|loop|"
            r"manager|staff|discount\s*approv)\b",
            re.I,
        ),
    ),
    (
        "menu",
        re.compile(
            r"\b(menu|item|price|combo|deal|category|modifier|add\s*on|"
            r"dashboard.*item|update.*menu)\b",
            re.I,
        ),
    ),
    (
        "network",
        re.compile(
            r"\b(wifi|internet|network|connection|offline|online|server|"
            r"no\s*internet|connected)\b",
            re.I,
        ),
    ),
    (
        "billing",
        re.compile(
            r"\b(payment|bill|plan|subscription|overdue|invoice|branch|"
            r"upgrade|renew|bank\s*transfer|license|expir)\b",
            re.I,
        ),
    ),
    (
        "crash",
        re.compile(
            r"\b(crash|freeze|hang|stuck|not\s*respond|error|band|close|"
            r"force\s*close|restart\s*app)\b",
            re.I,
        ),
    ),
]

# Map sync-related to network for plan's 6 categories (sync → network bucket)
CATEGORY_NORMALIZE = {"sync": "network"}

# Issue title templates from keyword clusters within category
ISSUE_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    ("printer", "Receipt printer offline", re.compile(r"offline|not\s*work", re.I)),
    ("printer", "KOT printing blank tickets", re.compile(r"blank|khali|empty", re.I)),
    ("printer", "Bluetooth printer pairing", re.compile(r"bluetooth|pair|connect", re.I)),
    ("printer", "Printer general issues", re.compile(r"printer|print|kot", re.I)),
    ("network", "Orders not syncing to cloud", re.compile(r"sync|cloud|pending", re.I)),
    ("network", "WiFi connected but no internet", re.compile(r"wifi|internet|network", re.I)),
    ("network", "Day-end report totals mismatch", re.compile(r"day\s*end|report|total", re.I)),
    ("login", "Login loop after correct PIN", re.compile(r"loop|pin|password", re.I)),
    ("login", "Insufficient permissions for manager", re.compile(r"permission|manager|discount", re.I)),
    ("menu", "New menu items not showing on tablet", re.compile(r"new|add|not\s*show|nazar", re.I)),
    ("menu", "Wrong price on tablet vs admin", re.compile(r"price|galat|wrong", re.I)),
    ("billing", "Payment overdue despite payment", re.compile(r"overdue|paid|payment", re.I)),
    ("billing", "Multi-branch plan upgrade", re.compile(r"branch|plan|upgrade", re.I)),
    ("crash", "App crashes on reports", re.compile(r"crash|report|band", re.I)),
    ("general", "Vague / needs clarification", re.compile(r"^(help|not working|printer|sync|kya masla)", re.I)),
    ("general", "General support request", re.compile(r".+", re.I)),
]


@dataclass
class Message:
    text: str
    timestamp: str | None = None
    sender: str | None = None


@dataclass
class ClassifiedMessage:
    message: Message
    category: str
    issue_title: str


@dataclass
class IssueFrequency:
    issue_title: str
    category: str
    frequency: int
    sample_messages: list[str] = field(default_factory=list)


@dataclass
class AuditReport:
    timestamp: str
    input_file: str
    total_messages: int
    category_counts: dict[str, int]
    top_issues: list[IssueFrequency]
    mvp_csv_path: str
    frequency_json_path: str
    authors: list[str]
    demo_mode: bool = False


def parse_json_export(path: Path) -> list[Message]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "messages" in data:
        data = data["messages"]
    if not isinstance(data, list):
        raise ValueError("JSON export must be a list or {messages: [...]}")

    messages: list[Message] = []
    for item in data:
        if isinstance(item, str):
            messages.append(Message(text=item.strip()))
        elif isinstance(item, dict):
            text = (
                item.get("text")
                or item.get("body")
                or item.get("content")
                or item.get("message")
                or ""
            ).strip()
            if text:
                messages.append(
                    Message(
                        text=text,
                        timestamp=item.get("timestamp") or item.get("date"),
                        sender=item.get("sender") or item.get("from"),
                    )
                )
    return messages


def parse_csv_export(path: Path, text_column: str | None) -> list[Message]:
    messages: list[Message] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV has no header row")
        col = text_column
        if not col:
            for candidate in ("text", "body", "message", "content", "Message"):
                if candidate in reader.fieldnames:
                    col = candidate
                    break
        if not col:
            raise ValueError(
                f"Could not detect message column. Headers: {reader.fieldnames}. "
                "Use --text-column."
            )
        for row in reader:
            text = (row.get(col) or "").strip()
            if text and text.lower() not in ("message deleted", "<media omitted>"):
                messages.append(
                    Message(
                        text=text,
                        timestamp=row.get("timestamp") or row.get("date"),
                        sender=row.get("sender") or row.get("from"),
                    )
                )
    return messages


def load_messages(path: Path, text_column: str | None) -> list[Message]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return parse_json_export(path)
    if suffix == ".csv":
        return parse_csv_export(path, text_column)
    raise ValueError(f"Unsupported format: {suffix}. Use .json or .csv")


def classify_category(text: str) -> str:
    for name, pattern in CATEGORY_RULES:
        if pattern.search(text):
            normalized = CATEGORY_NORMALIZE.get(name, name)
            if normalized in CATEGORIES:
                return normalized
            return name if name in CATEGORIES else "general"
    return "general"


def classify_issue_title(text: str, category: str) -> str:
    for cat, title, pattern in ISSUE_PATTERNS:
        if cat == category and pattern.search(text):
            return title
    for _cat, title, pattern in ISSUE_PATTERNS:
        if pattern.search(text):
            return title
    return "General support request"


def classify_messages(messages: list[Message]) -> list[ClassifiedMessage]:
    return [
        ClassifiedMessage(
            message=m,
            category=classify_category(m.text),
            issue_title=classify_issue_title(m.text, classify_category(m.text)),
        )
        for m in messages
    ]


def aggregate_issues(classified: list[ClassifiedMessage]) -> list[IssueFrequency]:
    buckets: dict[tuple[str, str], IssueFrequency] = {}
    for cm in classified:
        key = (cm.category, cm.issue_title)
        if key not in buckets:
            buckets[key] = IssueFrequency(
                issue_title=cm.issue_title,
                category=cm.category,
                frequency=0,
            )
        buckets[key].frequency += 1
        if len(buckets[key].sample_messages) < 3:
            buckets[key].sample_messages.append(cm.message.text[:200])

    ranked = sorted(buckets.values(), key=lambda x: (-x.frequency, x.category, x.issue_title))
    return ranked


def needs_roman_urdu(sample_messages: list[str]) -> str:
    """Heuristic: Y if samples contain Roman Urdu markers."""
    urdu_markers = re.compile(
        r"\b(hai|nahi|kaise|kya|masla|chal|raha|ho\s*raha|kar|ke|bhai|"
        r"ghant|tablet|sync|printer)\b",
        re.I,
    )
    roman_chars = re.compile(r"[\u0600-\u06FF]")  # Arabic script (Urdu)
    for msg in sample_messages:
        if roman_chars.search(msg):
            return "Y"
        # Roman Urdu: Latin script with Urdu grammar markers
        latin_words = len(re.findall(r"[a-zA-Z]+", msg))
        if latin_words > 3 and urdu_markers.search(msg):
            return "Y"
    return "N"


def assign_author(index: int, authors: list[str]) -> str:
    if not authors:
        return ""
    return authors[index % len(authors)]


def write_mvp_csv(
    top_issues: list[IssueFrequency],
    path: Path,
    authors: list[str],
    *,
    demo: bool,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = top_issues[:30]
    # Pad to 30 rows if fewer issues found
    while len(rows) < 30:
        rows.append(
            IssueFrequency(
                issue_title="(Reserved — add from export)",
                category="general",
                frequency=0,
            )
        )

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "rank",
                "issue_title",
                "category",
                "frequency",
                "existing_doc",
                "author",
                "roman_urdu_needed",
                "notes",
            ],
        )
        writer.writeheader()
        for i, issue in enumerate(rows, start=1):
            writer.writerow(
                {
                    "rank": i,
                    "issue_title": issue.issue_title,
                    "category": issue.category,
                    "frequency": issue.frequency if not demo else f"DEMO:{issue.frequency}",
                    "existing_doc": "",
                    "author": assign_author(i - 1, authors),
                    "roman_urdu_needed": needs_roman_urdu(issue.sample_messages),
                    "notes": (
                        "Demo/sample data — replace with real WhatsApp export"
                        if demo
                        else ""
                    ),
                }
            )


def write_frequency_report(
    category_counts: dict[str, int],
    top_issues: list[IssueFrequency],
    path: Path,
) -> None:
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "category_counts": category_counts,
        "top_issues": [
            {
                "issue_title": i.issue_title,
                "category": i.category,
                "frequency": i.frequency,
                "sample_messages": i.sample_messages,
            }
            for i in top_issues[:30]
        ],
    }
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def run_audit(
    input_path: Path,
    authors: list[str],
    *,
    text_column: str | None = None,
    demo: bool = False,
) -> AuditReport:
    messages = load_messages(input_path, text_column)
    if not messages:
        raise ValueError(f"No messages parsed from {input_path}")

    classified = classify_messages(messages)
    category_counts = dict(Counter(cm.category for cm in classified))
    top_issues = aggregate_issues(classified)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    mvp_path = RESULTS_DIR / f"mvp_articles_{stamp}.csv"
    freq_path = RESULTS_DIR / f"frequency_report_{stamp}.json"

    write_mvp_csv(top_issues, mvp_path, authors, demo=demo)
    write_frequency_report(category_counts, top_issues, freq_path)

    return AuditReport(
        timestamp=datetime.now(UTC).isoformat(),
        input_file=str(input_path),
        total_messages=len(messages),
        category_counts=category_counts,
        top_issues=top_issues[:30],
        mvp_csv_path=str(mvp_path),
        frequency_json_path=str(freq_path),
        authors=authors,
        demo_mode=demo,
    )


def print_summary(report: AuditReport) -> None:
    print("\n=== Step 0.3 KB Content Audit ===\n")
    print(f"Input: {report.input_file} ({report.total_messages} messages)")
    if report.demo_mode:
        print("Mode: DEMO (sample data — not production frequencies)\n")
    print("Category counts:")
    for cat in CATEGORIES:
        count = report.category_counts.get(cat, 0)
        if count:
            print(f"  {cat:10} {count}")

    print(f"\nTop {min(10, len(report.top_issues))} issues:")
    for i, issue in enumerate(report.top_issues[:10], 1):
        print(f"  {i:2}. [{issue.category}] {issue.issue_title} ({issue.frequency})")

    print(f"\nMVP CSV:      {report.mvp_csv_path}")
    print(f"Frequency:    {report.frequency_json_path}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="KB content audit — Step 0.3")
    parser.add_argument("--input", "-i", type=Path, help="WhatsApp export (.json or .csv)")
    parser.add_argument(
        "--authors",
        default="",
        help="Comma-separated article authors for round-robin assignment",
    )
    parser.add_argument("--text-column", help="CSV column name for message body")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run on bundled sample data (for testing categorizer only)",
    )
    args = parser.parse_args()

    authors = [a.strip() for a in args.authors.split(",") if a.strip()]

    if args.demo:
        input_path = _SPIKE_DIR / "sample_data" / "sample_messages.json"
        demo = True
    elif args.input:
        input_path = args.input
        demo = False
    else:
        print(
            "Provide --input path/to/whatsapp_export.json or use --demo for sample run.\n"
            "For production MVP list, export 3–6 months WhatsApp support history.",
            file=sys.stderr,
        )
        return 1

    if not input_path.exists():
        print(f"File not found: {input_path}", file=sys.stderr)
        return 1

    try:
        report = run_audit(input_path, authors, text_column=args.text_column, demo=demo)
    except Exception as exc:  # noqa: BLE001 — spike CLI
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print_summary(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
