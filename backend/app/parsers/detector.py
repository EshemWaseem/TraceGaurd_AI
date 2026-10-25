"""
Format detector — selects the dominant log format for a file.

Known limitation (documented per spec): selects a single format for the whole file.
Mixed-format files will have lines from the non-dominant format flagged as unrecognised.
This is by design for the PoC — all lines are either parsed or preserved, never silently discarded.
"""

import json
import re
from typing import Literal

LogFormat = Literal["json_application", "plaintext", "nginx_apache", "unknown"]

# Nginx/Apache Combined Log Format
_NGINX_RE = re.compile(
    r'^\S+ \S+ \S+ \[[^\]]+\] "[^"]*" \d{3} \S+'
)

# Python/Java plaintext: timestamp + level + message
_PLAINTEXT_RE = re.compile(
    r"^\d{4}[-/]\d{2}[-/]\d{2}"  # date prefix is sufficient as a signal
)


def _score_line(line: str) -> dict[LogFormat, int]:
    """Return a dict of format → match score (0 or 1) for one non-empty line."""
    stripped = line.strip()
    scores: dict[LogFormat, int] = {
        "json_application": 0,
        "nginx_apache": 0,
        "plaintext": 0,
    }
    if not stripped:
        return scores
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict):
            scores["json_application"] = 1
            return scores
    except json.JSONDecodeError:
        pass
    if _NGINX_RE.match(stripped):
        scores["nginx_apache"] = 1
    elif _PLAINTEXT_RE.match(stripped):
        scores["plaintext"] = 1
    return scores


def detect_format(content: str, sample_lines: int = 50) -> LogFormat:
    """
    Sample up to `sample_lines` non-empty lines and return the format
    that matches ≥ 80% of them. Falls back to 'unknown'.
    """
    lines = [l for l in content.splitlines() if l.strip()][:sample_lines]
    if not lines:
        return "unknown"

    totals: dict[LogFormat, int] = {
        "json_application": 0,
        "nginx_apache": 0,
        "plaintext": 0,
    }
    for line in lines:
        for fmt, score in _score_line(line).items():
            totals[fmt] += score

    threshold = 0.8 * len(lines)
    for fmt in ("json_application", "nginx_apache", "plaintext"):
        if totals[fmt] >= threshold:
            return fmt  # type: ignore[return-value]

    return "unknown"
