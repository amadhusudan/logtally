"""Configuration loading. Reads YAML pattern definitions, falls back to bundled defaults."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

from logtally.patterns import Pattern, PatternSet


def _load_yaml(config_path: str | Path | None) -> tuple[Any, str]:
    """Return (parsed_yaml, source_label). Reads from disk for a custom path,
    from the bundled package data for None."""
    if config_path is None:
        text = (files("logtally") / "_data" / "default.yaml").read_text(encoding="utf-8")
        return yaml.safe_load(text), "<bundled default>"

    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f), str(path)


def load_patterns(config_path: str | Path | None = None) -> PatternSet:
    """Load a PatternSet from a YAML config file.

    Args:
        config_path: Path to YAML config. If None, uses bundled default.

    Returns:
        A PatternSet ready to match against log lines.

    Raises:
        FileNotFoundError: If a custom path is given but doesn't exist.
        ValueError: If the config is malformed.
    """
    data, source = _load_yaml(config_path)

    if not isinstance(data, dict) or "patterns" not in data:
        raise ValueError(
            f"Config {source} is malformed. Expected a top-level 'patterns' key."
        )

    raw_patterns = data["patterns"]
    if not isinstance(raw_patterns, list) or not raw_patterns:
        raise ValueError(
            f"Config {source} must contain a non-empty 'patterns' list."
        )

    patterns: list[Pattern] = []
    for i, raw in enumerate(raw_patterns):
        if not isinstance(raw, dict):
            raise ValueError(f"Pattern #{i} in {source} is not a dict: {raw!r}")
        for required in ("name", "regex"):
            if required not in raw:
                raise ValueError(
                    f"Pattern #{i} in {source} missing required field '{required}'"
                )
        patterns.append(
            Pattern(
                name=raw["name"],
                regex=raw["regex"],
                severity=raw.get("severity", "info"),
                description=raw.get("description", ""),
            )
        )

    return PatternSet(patterns)
