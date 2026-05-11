"""CLI entry point."""

from __future__ import annotations

import argparse
import sys

from logtally import __version__
from logtally.config import load_patterns
from logtally.stream import stream_lines
from logtally.summary import aggregate, format_jsonl, format_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="logtally",
        description=(
            "Stream a log file (or stdin), match lines against configurable "
            "regex patterns, and produce a summary report."
        ),
        epilog=(
            "Examples:\n"
            "  logtally app.log\n"
            "  logtally app.log --top 20 --min-severity warn\n"
            "  logtally app.log --config my-patterns.yaml --json > matches.jsonl\n"
            "  cat app.log | logtally -\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "source",
        nargs="?",
        default=None,
        help="Path to log file. Omit or use '-' to read from stdin.",
    )
    parser.add_argument(
        "--config",
        "-c",
        default=None,
        help="Path to YAML pattern config. Defaults to bundled patterns.",
    )
    parser.add_argument(
        "--top",
        "-n",
        type=int,
        default=10,
        help="Number of top patterns to show in the summary (default: 10).",
    )
    parser.add_argument(
        "--min-severity",
        "-s",
        choices=["info", "warn", "error", "critical"],
        default=None,
        help="Only count matches at this severity or higher.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output matches as JSONL to stdout instead of a summary.",
    )
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Load patterns from config (or bundled default)
    try:
        pattern_set = load_patterns(args.config)
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if args.min_severity:
        try:
            pattern_set = pattern_set.filter_by_severity(args.min_severity)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2

    # Stream and aggregate
    try:
        lines = stream_lines(args.source)
        summary, matches = aggregate(lines, pattern_set, capture_matches=args.json)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130

    # Output
    if args.json:
        print(format_jsonl(matches))
    else:
        print(format_summary(summary, top_n=args.top))

    return 0


if __name__ == "__main__":
    sys.exit(main())
