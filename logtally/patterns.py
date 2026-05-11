"""Pattern compilation and matching.

A Pattern wraps a compiled regex with a name and severity. PatternSet
matches a line against all patterns and returns matches.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Severity levels in increasing order. Used for sorting and filtering.
SEVERITY_ORDER = ["info", "warn", "error", "critical"]


@dataclass
class Pattern:
    """A named regex pattern with severity and optional description."""

    name: str
    regex: str
    severity: str = "info"
    description: str = ""
    _compiled: re.Pattern = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Compile up-front. Cheaper to do once than per-line.
        try:
            self._compiled = re.compile(self.regex, re.IGNORECASE)
        except re.error as e:
            raise ValueError(
                f"Invalid regex for pattern '{self.name}': {self.regex!r} ({e})"
            ) from e

        if self.severity not in SEVERITY_ORDER:
            raise ValueError(
                f"Pattern '{self.name}' has unknown severity '{self.severity}'. "
                f"Must be one of: {SEVERITY_ORDER}"
            )

    def matches(self, line: str) -> bool:
        """Return True if the pattern matches anywhere in the line."""
        return self._compiled.search(line) is not None


@dataclass
class Match:
    """A single match: which pattern fired on which line."""

    line_number: int
    line: str
    pattern: Pattern


class PatternSet:
    """A collection of patterns to match against each log line."""

    def __init__(self, patterns: list[Pattern]) -> None:
        if not patterns:
            raise ValueError("PatternSet requires at least one pattern.")
        self.patterns = patterns

    def find_matches(self, line: str, line_number: int) -> list[Match]:
        """Return all patterns that match this line. A line can hit many."""
        return [
            Match(line_number=line_number, line=line, pattern=p)
            for p in self.patterns
            if p.matches(line)
        ]

    def filter_by_severity(self, min_severity: str) -> PatternSet:
        """Return a new PatternSet with only patterns at or above min_severity."""
        if min_severity not in SEVERITY_ORDER:
            raise ValueError(f"Unknown severity: {min_severity}")
        threshold = SEVERITY_ORDER.index(min_severity)
        kept = [
            p for p in self.patterns if SEVERITY_ORDER.index(p.severity) >= threshold
        ]
        if not kept:
            raise ValueError(
                f"No patterns at severity >= {min_severity}. Available: "
                f"{sorted({p.severity for p in self.patterns})}"
            )
        return PatternSet(kept)
