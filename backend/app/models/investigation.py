"""Typed investigation model for TraceGuard AI Phase 2.

Separates deterministic evidence from optional AI-generated reasoning.
All fields are optional-safe — absent data produces Inconclusive results,
never fabricated ones.
"""

from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Sub-structures produced by the correlation layer
# ---------------------------------------------------------------------------

class TimelineSegment(BaseModel):
    """One time bucket in the log timeline."""
    start: str                    # ISO-8601 UTC
    end: str                      # ISO-8601 UTC
    event_count: int
    error_count: int
    warn_count: int
    info_count: int
    debug_count: int


class CorrelationGroup(BaseModel):
    """A cluster of events sharing a normalised error pattern or correlation ID."""
    pattern: str                           # normalised key used for grouping
    representative_message: str            # first raw message in the group
    occurrences: int
    line_numbers: List[int]
    services: List[str]                    # distinct services involved
    first_seen: Optional[str] = None       # ISO-8601 UTC
    last_seen: Optional[str] = None        # ISO-8601 UTC


class ErrorBurst(BaseModel):
    """A dense window of errors exceeding the burst threshold."""
    start: str                             # ISO-8601 UTC of first error
    end: str                               # ISO-8601 UTC of last error
    error_count: int
    line_numbers: List[int]
    services: List[str]
    window_seconds: int


class ServiceImpact(BaseModel):
    """Per-service summary of errors and a computed impact score (0–100)."""
    service: str
    error_count: int
    warn_count: int
    total_events: int
    impact_score: int                      # 0–100; higher = more impacted


# ---------------------------------------------------------------------------
# AI reasoning envelope (optional, bounded)
# ---------------------------------------------------------------------------

class AIReasoning(BaseModel):
    """Output from the optional AI reasoning layer.

    Present only when AI mode is active AND succeeded. The engine validation
    layer verifies that all line_references exist in the parsed event set before
    accepting this output.
    """
    provider: str                          # e.g. "gemini", "openai", "mock_deterministic"
    model: Optional[str] = None
    summary: str                           # ≤ 500 chars; what happened in plain English
    root_cause_hypothesis: Optional[str] = None   # ≤ 300 chars; may be None if inconclusive
    confidence: Literal["high", "medium", "low", "inconclusive"]
    alternative_explanations: List[str]    # ≤ 3 items
    recommended_next_steps: List[str]      # ≤ 5 items
    missing_information: List[str]         # what evidence would help
    line_references: List[int]             # validated to exist in parsed events
    injected_content_detected: bool = False  # True if prompt-injection defense flagged input


# ---------------------------------------------------------------------------
# Top-level investigation report
# ---------------------------------------------------------------------------

class InvestigationReport(BaseModel):
    """A complete, structured investigation for one log ingestion.

    Evidence-first: deterministic analysis is always present.
    AI reasoning is optional and clearly labelled.
    """
    # --- Identity ---
    filename: str
    engine_version: str = "2.0.0"
    analysis_mode: Literal["deterministic", "ai_assisted"]

    # --- Deterministic findings ---
    incident_start: Optional[str] = None   # earliest error timestamp (ISO-8601 UTC)
    incident_end: Optional[str] = None     # latest error timestamp (ISO-8601 UTC)
    severity_verdict: Literal["critical", "high", "medium", "low", "inconclusive"]
    severity_rationale: str                # brief explanation, ≤ 200 chars
    evidence_strength: Literal["strong", "moderate", "limited", "insufficient"] = "limited"
    root_cause_status: Literal["confirmed", "probable", "possible", "undetermined"] = "possible"
    analysis_method: Literal["rules_based", "ai_assisted", "backup_method"] = "rules_based"

    # --- Correlation layer ---
    timeline_segments: List[TimelineSegment]
    error_bursts: List[ErrorBurst]
    repeated_error_groups: List[CorrelationGroup]
    correlation_id_groups: List[CorrelationGroup]
    service_impacts: List[ServiceImpact]

    # --- Optional AI envelope ---
    ai_reasoning: Optional[AIReasoning] = None

    # --- Audit ---
    ai_was_attempted: bool = False
    ai_failure_reason: Optional[str] = None   # present when attempted but failed/timed-out
