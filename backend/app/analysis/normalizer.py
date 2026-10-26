"""Normaliser – timestamp parsing and severity canonicalisation."""
from datetime import timezone
from dateutil import parser as dateutil_parser

from ..models.schemas import ParsedEvent

_SEVERITY_MAP = {
    "fatal": "ERROR",
    "critical": "ERROR",
    "severe": "ERROR",
    "error": "ERROR",
    "err": "ERROR",
    "warn": "WARN",
    "warning": "WARN",
    "info": "INFO",
    "information": "INFO",
    "debug": "DEBUG",
    "trace": "DEBUG",
}


def normalise_event(event: ParsedEvent) -> ParsedEvent:
    """Normalise timestamp to ISO-8601 UTC and severity to canonical value.

    On timestamp parse failure, timestamp remains None and timestamp_parsed=False.
    """
    # --- Timestamp ---
    raw_ts = event.timestamp
    if raw_ts:
        try:
            dt = dateutil_parser.parse(raw_ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt_utc = dt.astimezone(timezone.utc)
            # ISO format: 2024-01-15T10:02:31+00:00 → strip offset, add Z
            iso = dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            event = event.model_copy(update={"timestamp": iso, "timestamp_parsed": True})
        except Exception:
            event = event.model_copy(update={"timestamp": None, "timestamp_parsed": False})
    else:
        event = event.model_copy(update={"timestamp_parsed": False})

    # --- Severity ---
    mapped = _SEVERITY_MAP.get(event.severity.lower(), None)
    if mapped:
        event = event.model_copy(update={"severity": mapped})

    return event
