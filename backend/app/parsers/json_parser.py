import json
from datetime import datetime, timezone
from typing import Optional

from dateutil import parser as dateutil_parser

from ..models.schemas import ParsedEvent, UnrecognisedLine

# Canonical severity map — covers common logging framework variations
SEVERITY_MAP: dict[str, str] = {
    "debug": "DEBUG",
    "trace": "DEBUG",
    "info": "INFO",
    "information": "INFO",
    "warn": "WARN",
    "warning": "WARN",
    "error": "ERROR",
    "err": "ERROR",
    "critical": "ERROR",
    "fatal": "ERROR",
    "severe": "ERROR",
}


def _parse_timestamp(value: object) -> tuple[Optional[str], bool]:
    """Return (iso8601_utc_string | None, parsed_ok)."""
    if value is None:
        return None, False
    try:
        if isinstance(value, (int, float)):
            # Treat as Unix epoch seconds
            dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
            return dt.isoformat(), True
        raw = str(value)
        dt = dateutil_parser.parse(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat(), True
    except Exception:
        return None, False


def parse_json_logs(content: str) -> tuple[list[ParsedEvent], list[UnrecognisedLine]]:
    """
    Parse one-JSON-object-per-line application logs.
    Preserves original line text and line numbers exactly.
    Lines that are not valid JSON are collected as unrecognised.
    """
    events: list[ParsedEvent] = []
    unrecognised: list[UnrecognisedLine] = []

    for line_number, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue  # blank lines are silently skipped (not flagged)

        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            unrecognised.append(
                UnrecognisedLine(
                    line_number=line_number,
                    raw=line,
                    reason="Not valid JSON",
                )
            )
            continue

        if not isinstance(obj, dict):
            unrecognised.append(
                UnrecognisedLine(
                    line_number=line_number,
                    raw=line,
                    reason="JSON value is not an object",
                )
            )
            continue

        # --- Field extraction (try common field name variants) ---
        timestamp_raw = (
            obj.get("timestamp")
            or obj.get("time")
            or obj.get("@timestamp")
            or obj.get("ts")
            or obj.get("datetime")
            or obj.get("date")
        )

        level_raw = (
            obj.get("level")
            or obj.get("severity")
            or obj.get("log_level")
            or obj.get("loglevel")
            or obj.get("lvl")
            or obj.get("priority")
        )

        message = str(
            obj.get("message")
            or obj.get("msg")
            or obj.get("text")
            or obj.get("body")
            or ""
        ).strip() or stripped  # fall back to raw JSON if no message field

        service = (
            obj.get("service")
            or obj.get("logger")
            or obj.get("name")
            or obj.get("app")
            or obj.get("component")
            or obj.get("source")
        )

        timestamp_str, timestamp_parsed = _parse_timestamp(timestamp_raw)

        severity = "UNKNOWN"
        if level_raw is not None:
            severity = SEVERITY_MAP.get(str(level_raw).strip().lower(), "UNKNOWN")

        events.append(
            ParsedEvent(
                line_number=line_number,
                timestamp=timestamp_str,
                timestamp_parsed=timestamp_parsed,
                severity=severity,  # type: ignore[arg-type]
                service=str(service).strip() if service is not None else None,
                message=message,
                raw=line,  # original line, never mutated
                format="json_application",
            )
        )

    return events, unrecognised
