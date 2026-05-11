"""Line streaming from files or stdin. Memory-efficient for large logs."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path


def stream_lines(source: str | Path | None) -> Iterator[str]:
    """Yield lines from a file path or stdin.

    Args:
        source: Path to log file. If None or "-", reads from stdin.

    Yields:
        Lines with trailing newlines stripped.

    Raises:
        FileNotFoundError: If source path does not exist.
    """
    if source is None or source == "-":
        yield from _stream_stdin()
        return

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Log file not found: {path}")

    # errors='replace' keeps us going through stray non-utf8 bytes.
    # Real logs are full of garbage; we don't want to crash mid-file.
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            yield line.rstrip("\n")


def _stream_stdin() -> Iterator[str]:
    """Stream lines from stdin, lenient about encoding."""
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(errors="replace")  # type: ignore[union-attr]
    for line in sys.stdin:
        yield line.rstrip("\n")
