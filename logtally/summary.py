"""Aggregation and reporting of matched lines."""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

from logtally.patterns import SEVERITY_ORDER, Match

# Common timestamp formats we try to detect at the start of a log line.
# Order matters: more specific first. The third tuple element flags whether
# the format carries a year — yearless formats default to 1900 in strptime,
# which makes time-range deltas nonsense, so we substitute the current year.
_TIMESTAMP_FORMATS = [
    # 2026-04-29 14:33:21,512
    (r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})(?:[.,]\d+)?", "%Y-%m-%d %H:%M:%S", True),
    # Apr 29 14:33:21
    (r"([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})", "%b %d %H:%M:%S", False),
    # 29/Apr/2026:14:33:21
    (r"(\d{1,2}/[A-Z][a-z]{2}/\d{4}:\d{2}:\d{2}:\d{2})", "%d/%b/%Y:%H:%M:%S", True),
]


def _parse_timestamp(line: str) -> datetime | None:
    """Try to pull a timestamp from the start of a line. Returns None on failure."""
    for pattern, fmt, has_year in _TIMESTAMP_FORMATS:
        m = re.search(pattern, line)
        if m:
            raw = m.group(1).replace("T", " ")
            try:
                ts = datetime.strptime(raw, fmt)
            except ValueError:
                continue
            if not has_year:
                ts = ts.replace(year=datetime.now().year)
            return ts
    return None


@dataclass
class Summary:
    """Aggregated results from a scan.

    Note the distinction:
      - matched_lines: count of lines that hit at least one pattern (each line counted once)
      - total_matches: total (pattern, line) hits across all patterns
    A single line can fire multiple patterns, so total_matches >= matched_lines.
    """

    total_lines: int = 0
    matched_lines: int = 0
    total_matches: int = 0
    pattern_counts: Counter = field(default_factory=Counter)
    severity_counts: Counter = field(default_factory=Counter)
    pattern_severities: dict[str, str] = field(default_factory=dict)
    pattern_descriptions: dict[str, str] = field(default_factory=dict)
    first_timestamp: datetime | None = None
    last_timestamp: datetime | None = None

    @property
    def match_rate(self) -> float:
        """Fraction of lines that triggered at least one pattern (0.0 to 1.0)."""
        if self.total_lines == 0:
            return 0.0
        return self.matched_lines / self.total_lines

    def record_line(self, matches: list[Match]) -> None:
        """Record all matches for a single line. Counts the line once."""
        if not matches:
            return
        self.matched_lines += 1
        for m in matches:
            self.total_matches += 1
            self.pattern_counts[m.pattern.name] += 1
            self.severity_counts[m.pattern.severity] += 1
            self.pattern_severities[m.pattern.name] = m.pattern.severity
            self.pattern_descriptions[m.pattern.name] = m.pattern.description

    def observe_timestamp(self, ts: datetime) -> None:
        if self.first_timestamp is None or ts < self.first_timestamp:
            self.first_timestamp = ts
        if self.last_timestamp is None or ts > self.last_timestamp:
            self.last_timestamp = ts


def aggregate(
    lines: Iterable[str], pattern_set, capture_matches: bool = False
) -> tuple[Summary, list[Match]]:
    """Stream lines, match against patterns, build a Summary.

    Args:
        lines: Iterable of log lines.
        pattern_set: PatternSet to match against.
        capture_matches: If True, return all Match objects for JSONL export.
                        If False, return empty list (saves memory on huge files).

    Returns:
        (summary, matches). Matches list is empty unless capture_matches=True.
    """
    summary = Summary()
    captured: list[Match] = []

    for line_no, line in enumerate(lines, start=1):
        summary.total_lines += 1
        ts = _parse_timestamp(line)
        if ts is not None:
            summary.observe_timestamp(ts)

        matches = pattern_set.find_matches(line, line_no)
        summary.record_line(matches)
        if capture_matches:
            captured.extend(matches)

    return summary, captured


def format_summary(summary: Summary, top_n: int = 10) -> str:
    """Format a Summary as a human-readable report."""
    lines: list[str] = []
    lines.append("[summary]")
    lines.append(f"  Total lines:     {summary.total_lines:>12,}")
    lines.append(f"  Matched lines:   {summary.matched_lines:>12,}")
    lines.append(f"  Total matches:   {summary.total_matches:>12,}")
    lines.append(f"  Match rate:      {summary.match_rate * 100:>11.2f}%")

    if summary.first_timestamp and summary.last_timestamp:
        delta = summary.last_timestamp - summary.first_timestamp
        lines.append(
            f"  Time range:      {summary.first_timestamp.isoformat()} "
            f"to {summary.last_timestamp.isoformat()} ({delta})"
        )

    if summary.severity_counts:
        lines.append("")
        lines.append("[by severity]")
        for sev in SEVERITY_ORDER:
            n = summary.severity_counts.get(sev, 0)
            if n > 0:
                lines.append(f"  {sev:<10} {n:>10,}")

    if summary.pattern_counts:
        lines.append("")
        lines.append(f"[top {top_n} patterns]")
        for i, (name, count) in enumerate(
            summary.pattern_counts.most_common(top_n), start=1
        ):
            sev = summary.pattern_severities.get(name, "info")
            desc = summary.pattern_descriptions.get(name, "")
            tail = f"  ({desc})" if desc else ""
            lines.append(f"  {i:>2}. {count:>8,}  [{sev:<8}] {name}{tail}")

    return "\n".join(lines)


def format_jsonl(matches: list[Match]) -> str:
    """Format matches as JSONL, one record per line."""
    out: list[str] = []
    for m in matches:
        record = {
            "line_number": m.line_number,
            "line": m.line,
            "pattern": m.pattern.name,
            "severity": m.pattern.severity,
        }
        out.append(json.dumps(record, ensure_ascii=False))
    return "\n".join(out)
