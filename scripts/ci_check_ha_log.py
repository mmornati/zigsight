#!/usr/bin/env python3
"""Fail if a Home Assistant log shows evidence of a ZigSight bug.

Used by ``make e2e`` and .github/workflows/integration-test.yaml after the
e2e bootstrap (including its soak period) succeeds. Looking only for
"ERROR ... custom_components.zigsight" on a single line misses a lot of what
Home Assistant actually logs for a broken custom integration:

* ``homeassistant.components.mqtt.client`` logs "Exception in <callback>
  when handling msg on 'zigbee2mqtt/...'" *without* "zigsight" on that line;
  the only evidence is the traceback below it, whose frames show
  ``/config/custom_components/zigsight/...`` file paths (slashes, not dots).
* ``homeassistant.helpers.entity_platform`` logs "Error adding entity ...
  for domain sensor with platform zigsight" at ERROR.
* ``homeassistant.util.async_``/``helpers.frame`` log "Detected blocking
  call ... custom integration 'zigsight'" (and other "Detected that custom
  integration 'zigsight' ..." reports) at WARNING - never fatal on its own,
  but real evidence of a bug.

The log is therefore split into *records*: a line starting with a Home
Assistant timestamp (``2026-09-24 10:00:00.123 LEVEL ...``) starts a record,
and every following line that doesn't (traceback frames, exception
messages, chained "During handling of the above exception" blocks) belongs
to it. A record is a problem when, matching ``zigsight`` case-insensitively
in both the dotted (``custom_components.zigsight``) and path
(``custom_components/zigsight``) forms:

1. its level is ERROR or CRITICAL and anything in it (header or traceback)
   mentions zigsight;
2. it carries a traceback with a ``custom_components[./]zigsight`` frame,
   whatever its level;
3. it matches ``Detected .*zigsight`` (blocking calls, deprecated API use).

A missing or empty log file is itself a failure: a gate that can't read its
input must not pass.

Usage: ``ci_check_ha_log.py <home-assistant.log>``. The log must be
captured without docker's per-line prefix (``docker compose logs
--no-log-prefix``) so record boundaries can be recognised.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# "2026-09-24 10:00:00.123 ERROR (MainThread) [logger] message"
RECORD_START_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\s+(?P<level>[A-Z]+)\b"
)
ZIGSIGHT_RE = re.compile(r"zigsight", re.IGNORECASE)
ZIGSIGHT_FRAME_RE = re.compile(r"custom_components[./]zigsight", re.IGNORECASE)
DETECTED_RE = re.compile(r"Detected .*zigsight", re.IGNORECASE)
TRACEBACK_RE = re.compile(r"^\s*Traceback \(most recent call last\):")
# Home Assistant colours its console log (level-coloured lines) even when
# docker captures it; the escapes would hide the timestamp at line start.
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
FAILING_LEVELS = frozenset({"ERROR", "CRITICAL", "FATAL"})
MAX_REPORTED_LINES = 30


@dataclass
class LogRecord:
    """One log record: its header line plus any continuation lines."""

    level: str | None
    lines: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        """Return the whole record as text."""
        return "\n".join(self.lines)

    @property
    def has_traceback(self) -> bool:
        """Return True if the record carries a Python traceback."""
        return any(TRACEBACK_RE.match(line) for line in self.lines)


def split_records(text: str) -> list[LogRecord]:
    """Split a log into records (header line + continuation lines)."""
    records: list[LogRecord] = []
    current: LogRecord | None = None
    for raw_line in text.splitlines():
        line = ANSI_ESCAPE_RE.sub("", raw_line)
        match = RECORD_START_RE.match(line)
        if match or current is None:
            current = LogRecord(match.group("level") if match else None)
            records.append(current)
        current.lines.append(line)
    return records


def classify_record(record: LogRecord) -> str | None:
    """Return why ``record`` is a ZigSight problem, or None if it isn't."""
    text = record.text
    if record.level in FAILING_LEVELS and ZIGSIGHT_RE.search(text):
        return f"{record.level} record mentioning zigsight"
    if record.has_traceback and ZIGSIGHT_FRAME_RE.search(text):
        return "traceback through custom_components/zigsight"
    if DETECTED_RE.search(text):
        return "Home Assistant 'Detected ...' report for zigsight"
    return None


def find_problems(text: str) -> list[str]:
    """Return a human-readable description of each problem found in ``text``."""
    problems: list[str] = []
    for record in split_records(text):
        reason = classify_record(record)
        if reason is None:
            continue
        shown = record.lines[:MAX_REPORTED_LINES]
        if len(record.lines) > MAX_REPORTED_LINES:
            shown.append(f"... ({len(record.lines) - MAX_REPORTED_LINES} more lines)")
        problems.append(f"{reason}:\n  " + "\n  ".join(shown))
    return problems


def main(argv: list[str]) -> int:
    """Check the log file named on the command line; 0 if clean."""
    if len(argv) != 2:
        print("usage: ci_check_ha_log.py <home-assistant.log>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    if not text.strip():
        print(f"::error::{path} is missing or empty; cannot verify the log is clean")
        return 1

    problems = find_problems(text)
    if problems:
        print(f"::error::Found {len(problems)} ZigSight-related problem(s) in {path}")
        for problem in problems:
            print(problem)
        return 1

    print(f"No ZigSight ERROR/CRITICAL/traceback/'Detected' evidence in {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
