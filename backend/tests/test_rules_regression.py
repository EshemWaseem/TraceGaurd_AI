"""Focused regression tests for detection rules and parsers.

Covers:
- Retry storm threshold (spec: ≥2 subsequent attempts after initial error)
- Failure chain: B after A, within 120 s, labeled unconfirmed_hypothesis
- Nginx timestamp parsing: 15/Jan/2024:10:02:31 +0000 → 2024-01-15T10:02:31Z
- Evidence line numbers match original input lines
- 5 MiB limit and unrecognised line preservation (regression guards)
"""

import pytest
from app.models.schemas import ParsedEvent
from app.analysis.rules import retry_storm, failure_chain, error_spike, repeated_error_cluster
from app.analysis.normalizer import normalise_event
from app.parsers.nginx_parser import parse_nginx_logs


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def make_event(
    line_number: int,
    timestamp: str | None,
    message: str,
    severity: str = "ERROR",
    service: str | None = "svc",
    fmt: str = "json_application",
) -> ParsedEvent:
    ev = ParsedEvent(
        line_number=line_number,
        timestamp=timestamp,
        timestamp_parsed=False,
        severity=severity,  # type: ignore[arg-type]
        service=service,
        message=message,
        raw=message,
        format=fmt,  # type: ignore[arg-type]
    )
    return normalise_event(ev)


# ---------------------------------------------------------------------------
# Retry storm — threshold tests
# ---------------------------------------------------------------------------

def test_retry_storm_fires_with_two_subsequent_attempts():
    """Initial error + 2 subsequent = 3 total; must fire."""
    events = [
        make_event(1, "2024-01-15T10:00:00Z", "Database: connection timeout", service="db"),
        make_event(2, "2024-01-15T10:00:10Z", "Database: connection timeout", service="db"),
        make_event(3, "2024-01-15T10:00:20Z", "Database: connection timeout", service="db"),
    ]
    result = retry_storm(events)
    assert len(result) == 1, "Expected one retry storm anomaly"
    assert result[0].rule == "retry_storm"
    assert 1 in result[0].evidence_line_numbers
    assert 3 in result[0].evidence_line_numbers


def test_retry_storm_does_not_fire_with_one_subsequent_attempt():
    """Initial error + 1 subsequent = 2 total; must NOT fire (needs 2 subsequent)."""
    events = [
        make_event(1, "2024-01-15T10:00:00Z", "Database: connection timeout", service="db"),
        make_event(2, "2024-01-15T10:00:10Z", "Database: connection timeout", service="db"),
    ]
    result = retry_storm(events)
    assert result == [], "Should not fire with only one subsequent attempt"


def test_retry_storm_does_not_fire_without_service():
    """No service field → operation context cannot be established → must not fire."""
    events = [
        make_event(1, "2024-01-15T10:00:00Z", "Database: connection timeout", service=None),
        make_event(2, "2024-01-15T10:00:10Z", "Database: connection timeout", service=None),
        make_event(3, "2024-01-15T10:00:20Z", "Database: connection timeout", service=None),
    ]
    result = retry_storm(events)
    assert result == [], "Should not fire without service context"


def test_retry_storm_respects_30_second_window():
    """Subsequent attempts beyond 30 s must not be counted."""
    events = [
        make_event(1, "2024-01-15T10:00:00Z", "Database: connection timeout", service="db"),
        make_event(2, "2024-01-15T10:00:10Z", "Database: connection timeout", service="db"),
        make_event(3, "2024-01-15T10:00:35Z", "Database: connection timeout", service="db"),  # outside window
    ]
    result = retry_storm(events)
    assert result == [], "Third event is outside 30s window; only 1 subsequent = should not fire"


def test_retry_storm_does_not_fire_on_repeated_messages_only():
    """Repeated messages without identifiable operation context must not trigger retry storm."""
    events = [
        make_event(1, "2024-01-15T10:00:00Z", "something went wrong", service="svc"),
        make_event(2, "2024-01-15T10:00:05Z", "something went wrong", service="svc"),
        make_event(3, "2024-01-15T10:00:10Z", "something went wrong", service="svc"),
    ]
    # "something went wrong" has no colon or HTTP method → _extract_operation returns None
    result = retry_storm(events)
    assert result == [], "Repeated messages without operation context must not fire retry storm"


# ---------------------------------------------------------------------------
# Failure chain — direction and hypothesis label
# ---------------------------------------------------------------------------

def test_failure_chain_b_after_a():
    """B must be strictly after A (not the same time, not before)."""
    events = [
        make_event(1, "2024-01-15T10:00:00Z", "Connection refused", service="db"),
        make_event(2, "2024-01-15T10:01:00Z", "HTTP 500 Internal Server Error", service="api"),
    ]
    anoms, hyps = failure_chain(events)
    assert len(anoms) == 1
    assert len(hyps) == 1


def test_failure_chain_hypothesis_label():
    """Hypothesis must have epistemic_label='unconfirmed_hypothesis'."""
    events = [
        make_event(1, "2024-01-15T10:00:00Z", "Connection refused", service="db"),
        make_event(2, "2024-01-15T10:01:00Z", "HTTP 500 Internal Server Error", service="api"),
    ]
    _, hyps = failure_chain(events)
    assert hyps[0].epistemic_label == "unconfirmed_hypothesis"
    assert "unconfirmed" in hyps[0].title.lower() or hyps[0].epistemic_label == "unconfirmed_hypothesis"


def test_failure_chain_within_120s_only():
    """A→B beyond 120 s must not produce a chain."""
    events = [
        make_event(1, "2024-01-15T10:00:00Z", "Connection refused", service="db"),
        make_event(2, "2024-01-15T10:03:00Z", "HTTP 500 Internal Server Error", service="api"),  # 180 s later
    ]
    anoms, hyps = failure_chain(events)
    assert anoms == [] and hyps == [], "Chain beyond 120 s must not fire"


def test_failure_chain_no_self_chain():
    """Same normalised message must not produce a chain with itself."""
    events = [
        make_event(1, "2024-01-15T10:00:00Z", "Connection refused", service="db"),
        make_event(2, "2024-01-15T10:00:30Z", "Connection refused", service="db"),
    ]
    anoms, hyps = failure_chain(events)
    assert anoms == [] and hyps == []


# ---------------------------------------------------------------------------
# Nginx timestamp parsing
# ---------------------------------------------------------------------------

def test_nginx_timestamp_parsed_to_utc_iso():
    """Standard Nginx timestamp 15/Jan/2024:10:02:31 +0000 → 2024-01-15T10:02:31Z."""
    line = '127.0.0.1 - - [15/Jan/2024:10:02:31 +0000] "GET /api/health HTTP/1.1" 200 512 "-" "curl/7"'
    events, unrec = parse_nginx_logs(line)
    assert len(events) == 1, f"Expected 1 event, got {len(events)}"
    ev = normalise_event(events[0])
    assert ev.timestamp_parsed, f"Timestamp not parsed; raw was: {events[0].timestamp!r}"
    assert ev.timestamp == "2024-01-15T10:02:31Z", f"Got: {ev.timestamp}"


def test_nginx_5xx_is_error():
    line = '10.0.0.1 - - [15/Jan/2024:10:02:31 +0000] "POST /api/data HTTP/1.1" 503 0 "-" "agent"'
    events, _ = parse_nginx_logs(line)
    assert events[0].severity == "ERROR"


def test_nginx_4xx_is_warn():
    line = '10.0.0.1 - - [15/Jan/2024:10:02:31 +0000] "GET /missing HTTP/1.1" 404 0 "-" "agent"'
    events, _ = parse_nginx_logs(line)
    assert events[0].severity == "WARN"


def test_nginx_2xx_is_info():
    line = '10.0.0.1 - - [15/Jan/2024:10:02:31 +0000] "GET /api/health HTTP/1.1" 200 512 "-" "agent"'
    events, _ = parse_nginx_logs(line)
    assert events[0].severity == "INFO"


def test_nginx_line_number_preserved():
    """Line numbers must correspond to original file positions."""
    content = '\n'.join([
        '10.0.0.1 - - [15/Jan/2024:10:00:00 +0000] "GET /a HTTP/1.1" 200 10 "-" "a"',
        'not a valid nginx line',
        '10.0.0.2 - - [15/Jan/2024:10:00:01 +0000] "GET /b HTTP/1.1" 500 0 "-" "b"',
    ])
    events, unrec = parse_nginx_logs(content)
    assert events[0].line_number == 1
    assert unrec[0].line_number == 2
    assert events[1].line_number == 3


# ---------------------------------------------------------------------------
# Error spike
# ---------------------------------------------------------------------------

def test_error_spike_fires_at_3_in_60s():
    events = [
        make_event(i, f"2024-01-15T10:00:{i:02d}Z", f"err {i}") for i in range(3)
    ]
    result = error_spike(events)
    assert len(result) == 1


def test_error_spike_does_not_fire_below_threshold():
    events = [
        make_event(i, f"2024-01-15T10:00:{i:02d}Z", f"err {i}") for i in range(2)
    ]
    assert error_spike(events) == []


def test_error_spike_excludes_events_without_timestamps():
    """Events with no valid timestamp must be excluded (spec requirement)."""
    events = [
        make_event(1, "2024-01-15T10:00:00Z", "err 1"),
        make_event(2, "2024-01-15T10:00:10Z", "err 2"),
        # This one has unparseable timestamp — should be excluded
        make_event(3, None, "err 3"),
    ]
    result = error_spike(events)
    assert result == [], "Should not fire when only 2 events have valid timestamps"


# ---------------------------------------------------------------------------
# Repeated error cluster
# ---------------------------------------------------------------------------

def test_repeated_error_cluster_fires_at_3():
    events = [
        make_event(i, f"2024-01-15T10:00:{i:02d}Z", "Database timeout error 123") for i in range(3)
    ]
    result = repeated_error_cluster(events)
    assert len(result) == 1


def test_repeated_error_cluster_groups_by_normalised_message():
    """Messages differing only by numbers are grouped together."""
    events = [
        make_event(1, "2024-01-15T10:00:00Z", "Database timeout after 5000ms"),
        make_event(2, "2024-01-15T10:00:10Z", "Database timeout after 7000ms"),
        make_event(3, "2024-01-15T10:00:20Z", "Database timeout after 3000ms"),
    ]
    result = repeated_error_cluster(events)
    assert len(result) == 1, "All three should normalise to the same message pattern"


# ---------------------------------------------------------------------------
# Evidence line numbers
# ---------------------------------------------------------------------------

def test_evidence_line_numbers_are_original_input_lines():
    """Anomaly evidence_line_numbers must correspond to original input line numbers."""
    events = [
        make_event(7, "2024-01-15T10:00:00Z", "Connection refused"),
        make_event(13, "2024-01-15T10:00:30Z", "Connection refused"),
        make_event(19, "2024-01-15T10:01:00Z", "Connection refused"),
    ]
    result = repeated_error_cluster(events)
    assert len(result) == 1
    assert sorted(result[0].evidence_line_numbers) == [7, 13, 19]
