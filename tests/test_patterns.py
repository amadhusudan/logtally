"""Tests for the patterns module."""

from __future__ import annotations

import pytest

from logtally.patterns import Pattern, PatternSet


def test_pattern_compiles_valid_regex():
    p = Pattern(name="t", regex=r"\bERROR\b")
    assert p.matches("this is an ERROR line")
    assert not p.matches("nothing to see here")


def test_pattern_is_case_insensitive():
    p = Pattern(name="t", regex=r"error")
    assert p.matches("ERROR happened")
    assert p.matches("Error happened")
    assert p.matches("error happened")


def test_pattern_rejects_invalid_regex():
    with pytest.raises(ValueError, match="Invalid regex"):
        Pattern(name="bad", regex="(unclosed")


def test_pattern_rejects_unknown_severity():
    with pytest.raises(ValueError, match="unknown severity"):
        Pattern(name="t", regex="x", severity="catastrophic")


def test_patternset_requires_at_least_one():
    with pytest.raises(ValueError, match="at least one"):
        PatternSet([])


def test_patternset_finds_multiple_matches_per_line():
    ps = PatternSet(
        [
            Pattern(name="err", regex="ERROR", severity="error"),
            Pattern(name="db", regex="database", severity="error"),
        ]
    )
    matches = ps.find_matches("ERROR connecting to database", line_number=1)
    assert len(matches) == 2
    assert {m.pattern.name for m in matches} == {"err", "db"}


def test_patternset_filter_by_severity():
    ps = PatternSet(
        [
            Pattern(name="i", regex="info", severity="info"),
            Pattern(name="w", regex="warn", severity="warn"),
            Pattern(name="e", regex="err", severity="error"),
            Pattern(name="c", regex="crit", severity="critical"),
        ]
    )
    filtered = ps.filter_by_severity("error")
    names = {p.name for p in filtered.patterns}
    assert names == {"e", "c"}


def test_patternset_filter_raises_if_nothing_left():
    ps = PatternSet([Pattern(name="i", regex="info", severity="info")])
    with pytest.raises(ValueError, match="No patterns at severity"):
        ps.filter_by_severity("critical")
