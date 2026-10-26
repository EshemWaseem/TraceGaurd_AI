"""Plaintext log parser — supports Python/Java-style logs with stack trace continuations.

Matches lines of the form:
    2024-01-15 10:02:05,123 ERROR service.name Something went wrong
    2024-01-15T10:02:05Z ERROR Something went wrong

Continuation lines (indented or starting with "at ", "Caused by:", "...") are grouped
into the preceding event and their line numbers are included in line_range.
"""

import re
from typing import List, Tuple, Optional

from ..models.schemas import ParsedEvent, UnrecognisedLine

# Primary log line: timestamp, level, optional service/logger, message
_PRIMARY_RE = re.compile(
    r"^(?P<timestamp>\d{4}[-/]\d{2}[-/]\d{2}[T \t]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)"
    r"\s+"
    r"(?P<level>DEBUG|INFO|WARN(?:ING)?|ERROR|CRITICAL|FATAL|SEVERE)"
    r"(?:\s+(?P<service>\S+))?"
    r"\s+(?P<message>.+)$",
    re.IGNORECASE,
)

# Continuation: indented line, or Java "at …", "Caused by:", "..."
_CONTINUATION_RE = re.compile(
    r"^(?:\s{2,}|at\s|\.\.\.|Caused by:)",
)


def parse_plaintext_logs(
    content: str,
) -> Tuple[List[ParsedEvent], List[UnrecognisedLine]]:
    events: List[ParsedEvent] = []
    unrecognised: List[UnrecognisedLine] = []

    lines = content.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue

        m = _PRIMARY_RE.match(line)
        if not m:
            unrecognised.append(UnrecognisedLine(
                line_number=i + 1,
                raw=line,
                reason="Plaintext: line does not match primary log format",
            ))
            i += 1
            continue

        # Gather continuation lines for stack traces
        start_line = i + 1  # 1-indexed
        raw_lines: List[str] = [line]
        j = i + 1
        while j < len(lines) and _CONTINUATION_RE.match(lines[j]):
            raw_lines.append(lines[j])
            j += 1

        end_line = i + len(raw_lines)  # 1-indexed inclusive
        line_range = [start_line, end_line] if len(raw_lines) > 1 else None

        level_raw = m.group("level").upper()
        # Normalise at parse time for convenience (normalizer.py will also normalise)
        level_map = {
            "WARNING": "WARN", "FATAL": "ERROR", "CRITICAL": "ERROR", "SEVERE": "ERROR",
        }
        level = level_map.get(level_raw, level_raw)

        events.append(ParsedEvent(
            line_number=start_line,
            line_range=line_range,
            timestamp=m.group("timestamp"),
            timestamp_parsed=False,   # normaliser handles
            severity=level,           # type: ignore[arg-type]
            service=m.group("service"),
            message=m.group("message").strip(),
            raw="\n".join(raw_lines),
            format="plaintext",
        ))

        i = j

    return events, unrecognised
