import os
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def test_analyze_json_fixture_schema():
    """POST /api/analyze with the JSON fixture returns a valid AnalysisResult."""
    fixture_path = os.path.join(FIXTURES_DIR, "sample_json.log")
    with open(fixture_path, "rb") as f:
        response = client.post(
            "/api/analyze",
            files={"file": ("sample_json.log", f, "text/plain")},
        )
    assert response.status_code == 200, response.text
    data = response.json()

    # Top-level keys
    assert set(data.keys()) >= {
        "filename", "summary", "events", "anomalies", "hypotheses", "unrecognised_lines"
    }
    # Summary counts are non-negative integers
    summary = data["summary"]
    assert summary["total_lines"] > 0
    assert summary["parsed_events"] > 0
    assert summary["parsed_events"] == len(data["events"])
    assert summary["unrecognised_lines"] == len(data["unrecognised_lines"])
    assert summary["error_count"] == sum(1 for e in data["events"] if e["severity"] == "ERROR")
    assert summary["warn_count"] == sum(1 for e in data["events"] if e["severity"] == "WARN")


# ---------------------------------------------------------------------------
# Line number integrity (Slice 1 foundation for the full evidence check in Slice 2)
# ---------------------------------------------------------------------------

def test_line_numbers_positive_and_raw_preserved():
    """Every parsed event has a positive line_number and non-empty raw field."""
    fixture_path = os.path.join(FIXTURES_DIR, "sample_json.log")
    with open(fixture_path, "rb") as f:
        response = client.post(
            "/api/analyze",
            files={"file": ("sample_json.log", f, "text/plain")},
        )
    data = response.json()
    for event in data["events"]:
        assert event["line_number"] >= 1, f"Bad line_number on event: {event}"
        assert event["raw"], f"Empty raw on event at line {event['line_number']}"

    for unrecognised in data["unrecognised_lines"]:
        assert unrecognised["line_number"] >= 1
        assert unrecognised["raw"]
        assert unrecognised["reason"]


# ---------------------------------------------------------------------------
# Unrecognised line detection
# ---------------------------------------------------------------------------

def test_unrecognised_lines_captured():
    """The non-JSON line in the fixture is flagged, not silently discarded."""
    fixture_path = os.path.join(FIXTURES_DIR, "sample_json.log")
    with open(fixture_path, "rb") as f:
        response = client.post(
            "/api/analyze",
            files={"file": ("sample_json.log", f, "text/plain")},
        )
    data = response.json()
    assert len(data["unrecognised_lines"]) >= 1
    reasons = [u["reason"] for u in data["unrecognised_lines"]]
    assert any("JSON" in r for r in reasons)


# ---------------------------------------------------------------------------
# Timestamp-less event handled
# ---------------------------------------------------------------------------

def test_event_without_timestamp_included():
    """Events with no timestamp are still parsed and appear at end of sorted list."""
    fixture_path = os.path.join(FIXTURES_DIR, "sample_json.log")
    with open(fixture_path, "rb") as f:
        response = client.post(
            "/api/analyze",
            files={"file": ("sample_json.log", f, "text/plain")},
        )
    data = response.json()
    events = data["events"]
    no_ts = [e for e in events if not e["timestamp_parsed"]]
    assert len(no_ts) >= 1, "Expected at least one event without a valid timestamp"
    # Events without timestamps must appear after all timestamped events
    last_ts_idx = max(
        (i for i, e in enumerate(events) if e["timestamp_parsed"]), default=-1
    )
    first_no_ts_idx = min(
        (i for i, e in enumerate(events) if not e["timestamp_parsed"]), default=len(events)
    )
    assert first_no_ts_idx > last_ts_idx, (
        "Timestamp-less events should be sorted after timestamped events"
    )


# ---------------------------------------------------------------------------
# Error boundaries
# ---------------------------------------------------------------------------

def test_analyze_size_limit_json_body():
    """Pasted content exceeding 5 MB is rejected with 413."""
    big_content = '{"level":"INFO","message":"x"}\n' * 200_000  # ~6 MB
    response = client.post(
        "/api/analyze",
        json={"content": big_content, "filename": "big.log"},
    )
    assert response.status_code == 413


def test_analyze_empty_input():
    """Empty input returns 422."""
    response = client.post(
        "/api/analyze",
        json={"content": "   ", "filename": "empty.log"},
    )
    assert response.status_code == 422


def test_analyze_paste_path():
    """JSON body (paste path) also returns a valid AnalysisResult."""
    content = (
        '{"timestamp":"2024-01-15T10:00:00Z","level":"ERROR","message":"DB timeout","service":"db"}\n'
        '{"timestamp":"2024-01-15T10:00:05Z","level":"INFO","message":"Retry","service":"db"}\n'
    )
    response = client.post(
        "/api/analyze",
        json={"content": content, "filename": "pasted.log"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["parsed_events"] == 2
    assert data["filename"] == "pasted.log"
