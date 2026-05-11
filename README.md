# logtally

**Stream a log, match it against configurable regex patterns, get a summary report.**
Memory-efficient (handles files larger than RAM), zero-config for common patterns, JSONL output for pipelines.

[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Tests](https://github.com/amadhusudan/logtally/actions/workflows/tests.yml/badge.svg)](https://github.com/amadhusudan/logtally/actions/workflows/tests.yml)

---

## Why

`grep` is great when you know exactly what you're looking for. `cProfile`-style heavyweight log analyzers are overkill for "what broke in the last hour?" `logtally` is the in-between: point it at a log, get an honest breakdown of what's in there — by pattern, by severity, with a time range — in one command.

It's particularly useful when:

- You inherited a service and want to know what kinds of errors are normal vs. new
- A deployment went sideways and you want to find the noisy patterns fast
- You need to feed structured match data into another tool via JSONL

## What it looks like

```
$ logtally examples/sample-custom.log

[summary]
  Total lines:               55
  Matched lines:             39
  Total matches:             65
  Match rate:            70.91%
  Time range:      2026-04-29T09:00:01 to 2026-04-29T12:10:01 (3:10:00)

[by severity]
  info                7
  warn               24
  error              33
  critical            1

[top 10 patterns]
   1.       18  [error   ] generic_error  (Generic error-level log line)
   2.       12  [warn    ] generic_warning  (Generic warning-level log line)
   3.        5  [info    ] startup  (Service startup signal)
   4.        5  [warn    ] retry  (Operation was retried)
   5.        4  [error   ] connection_refused  (TCP connection refused by remote)
   6.        3  [warn    ] http_4xx  (HTTP 4xx response status)
   7.        3  [error   ] auth_failure  (Failed authentication or authorization)
   8.        3  [error   ] http_5xx  (HTTP 5xx response status)
   9.        2  [error   ] db_error  (Database error)
  10.        2  [warn    ] rate_limit  (Request was rate limited)
```

Note: a single line can match multiple patterns (e.g. an HTTP 500 line might also be a `generic_error`), which is why `Total matches` (65) is higher than `Matched lines` (39).

## Install

From source (only path for now; PyPI publishing is on the roadmap):

```bash
git clone https://github.com/amadhusudan/logtally.git
cd logtally
pip install -e .
```

The only runtime dependency is `pyyaml`.

## Usage

```bash
# Default: scan a file with bundled patterns, print summary
logtally app.log

# Show only top 20 patterns
logtally app.log --top 20

# Filter to error and critical only
logtally app.log --min-severity error

# Pipe from stdin
cat app.log | logtally -
journalctl -u myservice | logtally -

# Output every match as JSONL for downstream processing
logtally app.log --json > matches.jsonl

# Use your own pattern set
logtally app.log --config my-patterns.yaml
```

### CLI reference

```
positional arguments:
  source                       Path to log file. Omit or use '-' for stdin.

options:
  --config, -c PATH            Path to YAML pattern config. Defaults to bundled patterns.
  --top, -n N                  Number of top patterns to show (default: 10).
  --min-severity, -s LEVEL     Only count matches at this severity or higher.
                               Choices: info, warn, error, critical.
  --json                       Output matches as JSONL to stdout instead of summary.
  --version, -v                Show version and exit.
```

## Try it out

The repo ships with several sample logs in [`examples/`](examples/) covering common formats. They double as smoke tests for the bundled patterns:

| File | Format | What's in it |
|---|---|---|
| [`sample-custom.log`](examples/sample-custom.log) | Generic app log — `2026-04-29 09:00:01 LEVEL logger msg` | deadlocks, retries, 4xx/5xx, auth failures, OOM |
| [`sample-syslog.log`](examples/sample-syslog.log) | RFC3164 syslog (yearless) — `Apr 29 09:00:01 host …` | service lifecycle, OOM, retries |
| [`sample-systemd.log`](examples/sample-systemd.log) | `journalctl` default output | unit transitions, sshd auth failures, kernel OOM kill |
| [`sample-nginx-access.log`](examples/sample-nginx-access.log) | nginx/Apache Combined Log Format | HTTP 4xx/5xx breakdown, bot scanners |
| [`sample-json.log`](examples/sample-json.log) | JSONL (zap/zerolog/pino style) | structured logs with `level`/`msg`/contextual fields |

```bash
# HTTP status breakdown from nginx access logs
logtally examples/sample-nginx-access.log

# Only error/critical from structured JSON logs
logtally examples/sample-json.log --min-severity error

# systemd journal scan piped through, then count critical patterns
logtally examples/sample-systemd.log --json | jq -r '.pattern' | sort | uniq -c
```

## Patterns

`logtally` ships with a default pattern set covering common signals: HTTP errors, timeouts, auth failures, deadlocks, OOMs, deprecation warnings, retries, and more. See [`logtally/_data/default.yaml`](logtally/_data/default.yaml) for the full list.

You can write your own pattern file in the same format:

```yaml
patterns:
  - name: my_custom_signal
    regex: "checkout flow stuck for user_id=\\d+"
    severity: error
    description: "Checkout hang"

  - name: gateway_5xx
    regex: " 5\\d{2} .* upstream "
    severity: critical
    description: "5xx response from upstream gateway"
```

Then run:

```bash
logtally app.log --config my-patterns.yaml
```

A pattern can match anywhere in a line (regexes use Python `re.search` with case-insensitive matching). One line can fire multiple patterns; each fired pattern counts independently in the top-N report.

## Design notes

A few choices worth knowing about:

- **Streaming, not loading.** `logtally` reads one line at a time. A 10 GB log file uses ~10 MB of memory, not 10 GB.
- **Lenient encoding.** Real-world logs contain random non-UTF-8 bytes. `logtally` uses `errors='replace'` rather than crashing mid-scan.
- **No SQL, no database, no daemon.** It's a single Python process that reads stdin or a file and prints to stdout. Compose it with shell pipelines.
- **JSONL output is the integration story.** If you want a dashboard, alerting, or trend analysis, pipe `--json` output into whatever tool already does that well.

## Performance

`logtally` is regex-bound, which means a few simple rules apply:

- More patterns = slower scan (each pattern is tried against each line)
- Anchored or specific patterns are faster than greedy ones
- The bundled default set processes roughly 200K–400K lines/second on a modern laptop CPU

If you're scanning gigabyte-scale logs and want hard numbers, profile your specific config with [`sentinel-trace`](https://github.com/amadhusudan/sentinel-trace).

## Testing

```bash
pip install -e ".[dev]"
pytest -v
```

Tests cover pattern compilation, severity filtering, line streaming (including encoding edge cases), aggregation logic, timestamp parsing (ISO, yearless syslog, and Apache/nginx formats), and output formatting. CI runs the suite against Python 3.9-3.12 on every push and pull request.

## Roadmap

- `--bucket 1h` — time-bucketed match counts for spotting bursts
- `--follow` / `-f` — tail mode (like `tail -f`)
- Anomaly detection — flag patterns whose rate jumps significantly within a time window
- Multi-file aggregation — `logtally logs/*.log` with per-file breakdown
- Pre-built pattern packs for nginx, syslog, Kubernetes events
- PyPI publish

## License

Apache 2.0. See [LICENSE](LICENSE).
