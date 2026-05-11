"""Tests for the summary module."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from logtally.patterns import Pattern, PatternSet
from logtally.stream import stream_lines
from logtally.summary import _parse_timestamp, aggregate, format_jsonl, format_summary

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def _ps():
    return PatternSet(
        [
            Pattern(name="err", regex=r"\bERROR\b", severity="error"),
            Pattern(name="warn", regex=r"\bWARN\b", severity="warn"),
        ]
    )


def test_aggregate_counts_total_lines():
    lines = ["one", "two", "three"]
    summary, _ = aggregate(lines, _ps())
    assert summary.total_lines == 3
    assert summary.matched_lines == 0
    assert summary.total_matches == 0


def test_aggregate_counts_matches_per_pattern():
    lines = [
        "INFO doing fine",
        "ERROR oh no",
        "ERROR oh no again",
        "WARN something off",
    ]
    summary, _ = aggregate(lines, _ps())
    assert summary.total_lines == 4
    assert summary.matched_lines == 3
    assert summary.total_matches == 3
    assert summary.pattern_counts["err"] == 2
    assert summary.pattern_counts["warn"] == 1


def test_aggregate_one_line_can_hit_multiple_patterns():
    ps = PatternSet(
        [
            Pattern(name="err", regex="error", severity="error"),
            Pattern(name="db", regex="database", severity="error"),
        ]
    )
    summary, _ = aggregate(["error in database"], ps)
    assert summary.total_lines == 1
    assert summary.matched_lines == 1  # one line, even though two patterns fired
    assert summary.total_matches == 2
    assert summary.pattern_counts["err"] == 1
    assert summary.pattern_counts["db"] == 1


def test_aggregate_captures_matches_when_requested():
    lines = ["ERROR a", "ok", "ERROR b"]
    _, matches = aggregate(lines, _ps(), capture_matches=True)
    assert len(matches) == 2
    assert matches[0].line_number == 1
    assert matches[1].line_number == 3


def test_aggregate_skips_capture_by_default():
    lines = ["ERROR x"] * 1000
    _, matches = aggregate(lines, _ps(), capture_matches=False)
    assert matches == []  # memory-safe path


def test_aggregate_extracts_timestamps():
    lines = [
        "2026-04-29 09:00:01 INFO start",
        "2026-04-29 10:30:00 ERROR bad",
        "2026-04-29 11:00:00 INFO end",
    ]
    summary, _ = aggregate(lines, _ps())
    assert summary.first_timestamp is not None
    assert summary.last_timestamp is not None
    assert summary.first_timestamp.hour == 9
    assert summary.last_timestamp.hour == 11


def test_match_rate():
    lines = ["ERROR a", "ok", "ERROR b", "ok"]
    summary, _ = aggregate(lines, _ps())
    assert summary.match_rate == 0.5


def test_match_rate_with_no_lines():
    summary, _ = aggregate([], _ps())
    assert summary.match_rate == 0.0


def test_format_summary_includes_total_and_top():
    lines = ["ERROR x", "ERROR y", "WARN z"]
    summary, _ = aggregate(lines, _ps())
    text = format_summary(summary, top_n=5)
    assert "Total lines" in text
    assert "err" in text
    assert "warn" in text


def test_format_jsonl_is_valid_json_per_line():
    lines = ["ERROR a", "WARN b"]
    _, matches = aggregate(lines, _ps(), capture_matches=True)
    out = format_jsonl(matches)
    records = [json.loads(line) for line in out.split("\n")]
    assert len(records) == 2
    assert records[0]["pattern"] == "err"
    assert records[1]["pattern"] == "warn"
    assert records[0]["severity"] == "error"


# ---- timestamp parsing ---------------------------------------------------


def test_parse_timestamp_iso_with_year():
    ts = _parse_timestamp("2026-04-29 14:33:21 INFO start")
    assert ts is not None
    assert (ts.year, ts.month, ts.day) == (2026, 4, 29)
    assert (ts.hour, ts.minute, ts.second) == (14, 33, 21)


def test_parse_timestamp_iso_with_milliseconds():
    ts = _parse_timestamp("2026-04-29T14:33:21.512 INFO start")
    assert ts is not None
    assert ts.year == 2026
    assert ts.hour == 14


def test_parse_timestamp_apache_style_with_year():
    ts = _parse_timestamp('127.0.0.1 - - [29/Apr/2026:14:33:21 +0000] "GET / HTTP/1.1" 200 12')
    assert ts is not None
    assert (ts.year, ts.month, ts.day) == (2026, 4, 29)
    assert ts.hour == 14


def test_parse_timestamp_yearless_syslog_uses_current_year():
    # Regression: previously defaulted to year 1900, which made deltas nonsense.
    ts = _parse_timestamp("Apr 29 14:33:21 web01 app: hello")
    assert ts is not None
    assert ts.year == datetime.now().year
    assert ts.year != 1900
    assert (ts.month, ts.day, ts.hour) == (4, 29, 14)


def test_parse_timestamp_returns_none_on_no_match():
    assert _parse_timestamp("no timestamp anywhere in this line") is None


# ---- sample-file integration --------------------------------------------


def test_aggregate_on_sample_custom_uses_embedded_year():
    sample = EXAMPLES_DIR / "sample-custom.log"
    summary, _ = aggregate(stream_lines(sample), _ps())
    assert summary.first_timestamp is not None
    assert summary.last_timestamp is not None
    assert summary.first_timestamp.year == 2026
    assert summary.last_timestamp.year == 2026


def test_aggregate_on_sample_syslog_substitutes_current_year():
    sample = EXAMPLES_DIR / "sample-syslog.log"
    summary, _ = aggregate(stream_lines(sample), _ps())
    current_year = datetime.now().year
    assert summary.first_timestamp is not None
    assert summary.last_timestamp is not None
    assert summary.first_timestamp.year == current_year
    assert summary.last_timestamp.year == current_year
    # The time-range delta must reflect the actual span, not span back to 1900.
    delta = summary.last_timestamp - summary.first_timestamp
    assert delta.days == 0
    assert 3 * 3600 <= delta.total_seconds() <= 4 * 3600


def test_aggregate_on_sample_systemd_substitutes_current_year():
    sample = EXAMPLES_DIR / "sample-systemd.log"
    summary, _ = aggregate(stream_lines(sample), _ps())
    current_year = datetime.now().year
    assert summary.first_timestamp is not None
    assert summary.last_timestamp is not None
    assert summary.first_timestamp.year == current_year
    assert summary.last_timestamp.year == current_year
    delta = summary.last_timestamp - summary.first_timestamp
    assert delta.days == 0
    # Sample spans 08:59:58 → 12:10:02 (~3h10m).
    assert 3 * 3600 <= delta.total_seconds() <= 4 * 3600


def test_aggregate_on_sample_nginx_access_uses_embedded_year():
    sample = EXAMPLES_DIR / "sample-nginx-access.log"
    summary, _ = aggregate(stream_lines(sample), _ps())
    assert summary.first_timestamp is not None
    assert summary.last_timestamp is not None
    assert summary.first_timestamp.year == 2026
    assert summary.first_timestamp.month == 4
    assert summary.first_timestamp.day == 29
    assert summary.first_timestamp.hour == 9
    assert summary.last_timestamp.hour == 12


def test_aggregate_on_sample_json_uses_embedded_year():
    sample = EXAMPLES_DIR / "sample-json.log"
    summary, _ = aggregate(stream_lines(sample), _ps())
    assert summary.first_timestamp is not None
    assert summary.last_timestamp is not None
    assert summary.first_timestamp.year == 2026
    assert summary.first_timestamp.hour == 9
    assert summary.last_timestamp.hour == 12
