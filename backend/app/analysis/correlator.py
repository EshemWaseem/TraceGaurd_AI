"""Correlation layer — groups events into patterns, builds timeline segments,
extracts correlation IDs, and detects cross-service error cascades.

All output is purely deterministic. No external calls are made here.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from ..models.schemas import Anomaly, ParsedEvent
from ..models.investigation import (
    CorrelationGroup,
    ErrorBurst,
    ServiceImpact,
    TimelineSegment,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CORR_ID_RE = re.compile(
    r"""(?:
        (?:correlation[_-]?id|request[_-]?id|trace[_-]?id|span[_-]?id|x[_-]?request[_-]?id)\s*[=:]\s*
        ([\w\-]{3,})
    )""",
    re.IGNORECASE | re.VERBOSE,
)


def _to_dt(ts: str) -> datetime:
    return datetime.fromisoformat(ts.rstrip("Z"))


def _extract_correlation_id(message: str) -> Optional[str]:
    m = _CORR_ID_RE.search(message)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def build_timeline_segments(
    events: List[ParsedEvent],
    window_seconds: int = 60,
) -> List[TimelineSegment]:
    """Divide the log timeline into non-overlapping 60-second buckets.

    Each bucket counts events by severity. Buckets with zero events are omitted.
    """
    timed = [e for e in events if e.timestamp_parsed and e.timestamp]
    if not timed:
        return []

    start = _to_dt(timed[0].timestamp)  # type: ignore[arg-type]
    end = _to_dt(timed[-1].timestamp)  # type: ignore[arg-type]

    segments: List[TimelineSegment] = []
    cursor = start
    while cursor <= end:
        bucket_end = cursor + timedelta(seconds=window_seconds)
        bucket_events = [
            e for e in timed
            if cursor <= _to_dt(e.timestamp) < bucket_end  # type: ignore[arg-type]
        ]
        if bucket_events:
            counts: Dict[str, int] = defaultdict(int)
            for e in bucket_events:
                counts[e.severity] += 1
            segments.append(
                TimelineSegment(
                    start=cursor.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    end=bucket_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    event_count=len(bucket_events),
                    error_count=counts["ERROR"],
                    warn_count=counts["WARN"],
                    info_count=counts["INFO"],
                    debug_count=counts["DEBUG"],
                )
            )
        cursor = bucket_end

    return segments


def group_repeated_errors(
    events: List[ParsedEvent],
    min_occurrences: int = 2,
) -> List[CorrelationGroup]:
    """Group ERROR events by normalised message (≥2 occurrences).

    Returns groups ordered by descending occurrence count.
    """
    import re as _re

    def _normalise(msg: str) -> str:
        msg = msg.lower()
        msg = _re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<uuid>", msg)
        msg = _re.sub(r"\d+", "<n>", msg)
        msg = _re.sub(r"\s+", " ", msg).strip()
        return msg

    groups: Dict[str, List[ParsedEvent]] = defaultdict(list)
    for e in events:
        if e.severity == "ERROR":
            groups[_normalise(e.message)].append(e)

    result: List[CorrelationGroup] = []
    for norm, evs in groups.items():
        if len(evs) >= min_occurrences:
            services = list(dict.fromkeys(e.service for e in evs if e.service))
            timestamps = [e.timestamp for e in evs if e.timestamp]
            result.append(
                CorrelationGroup(
                    pattern=norm[:120],
                    representative_message=evs[0].message[:200],
                    occurrences=len(evs),
                    line_numbers=[e.line_number for e in evs],
                    services=services,
                    first_seen=timestamps[0] if timestamps else None,
                    last_seen=timestamps[-1] if timestamps else None,
                )
            )

    result.sort(key=lambda g: g.occurrences, reverse=True)
    return result


def extract_correlation_groups(
    events: List[ParsedEvent],
) -> List[CorrelationGroup]:
    """Find events sharing an explicit correlation / request ID in their message."""
    by_corr: Dict[str, List[ParsedEvent]] = defaultdict(list)
    for e in events:
        cid = _extract_correlation_id(e.message)
        if cid:
            by_corr[cid].append(e)

    result: List[CorrelationGroup] = []
    for cid, evs in by_corr.items():
        if len(evs) < 2:
            continue
        services = list(dict.fromkeys(e.service for e in evs if e.service))
        timestamps = [e.timestamp for e in evs if e.timestamp]
        result.append(
            CorrelationGroup(
                pattern=f"correlation_id={cid}",
                representative_message=f"{len(evs)} events share correlation-id {cid}",
                occurrences=len(evs),
                line_numbers=[e.line_number for e in evs],
                services=services,
                first_seen=timestamps[0] if timestamps else None,
                last_seen=timestamps[-1] if timestamps else None,
            )
        )
    result.sort(key=lambda g: g.occurrences, reverse=True)
    return result


def build_error_bursts(
    events: List[ParsedEvent],
    window_seconds: int = 60,
    threshold: int = 3,
) -> List[ErrorBurst]:
    """Return distinct time windows that contain ≥ threshold ERROR events.

    Overlapping windows are merged into the single maximal burst.
    """
    errors = sorted(
        [e for e in events if e.severity == "ERROR" and e.timestamp_parsed and e.timestamp],
        key=lambda e: _to_dt(e.timestamp),  # type: ignore[arg-type]
    )
    if len(errors) < threshold:
        return []

    bursts: List[ErrorBurst] = []
    used: set[int] = set()

    for i, anchor in enumerate(errors):
        if i in used:
            continue
        t0 = _to_dt(anchor.timestamp)  # type: ignore[arg-type]
        window = [anchor]
        for j in range(i + 1, len(errors)):
            if j in used:
                continue
            if _to_dt(errors[j].timestamp) - t0 <= timedelta(seconds=window_seconds):  # type: ignore[arg-type]
                window.append(errors[j])
            else:
                break
        if len(window) >= threshold:
            for k, e in enumerate(errors):
                if e in window:
                    used.add(k)
            services = list(dict.fromkeys(e.service for e in window if e.service))
            bursts.append(
                ErrorBurst(
                    start=window[0].timestamp,  # type: ignore[arg-type]
                    end=window[-1].timestamp,  # type: ignore[arg-type]
                    error_count=len(window),
                    line_numbers=[e.line_number for e in window],
                    services=services,
                    window_seconds=window_seconds,
                )
            )

    return bursts


def compute_service_impacts(events: List[ParsedEvent]) -> List[ServiceImpact]:
    """Count errors/warnings per service and compute an impact score."""
    by_service: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    total_events: Dict[str, int] = defaultdict(int)

    for e in events:
        svc = e.service or "__unknown__"
        total_events[svc] += 1
        by_service[svc][e.severity] += 1

    impacts: List[ServiceImpact] = []
    for svc, counts in by_service.items():
        errors = counts.get("ERROR", 0)
        warns = counts.get("WARN", 0)
        total = total_events[svc]
        # Impact score: errors weight 3, warns weight 1, normalised to 0-100
        raw = errors * 3 + warns
        max_possible = total * 3
        score = round((raw / max_possible) * 100) if max_possible > 0 else 0

        impacts.append(
            ServiceImpact(
                service=svc,
                error_count=errors,
                warn_count=warns,
                total_events=total,
                impact_score=min(score, 100),
            )
        )

    impacts.sort(key=lambda s: s.impact_score, reverse=True)
    return impacts
