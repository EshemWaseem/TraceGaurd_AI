"""Investigation builder — assembles a complete InvestigationReport from
AnalysisResult + correlation layer + optional AI reasoning.

This module is the single entry-point for Phase 2 investigation generation.
It never replaces the existing AnalysisEngine; it augments its output.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from ..models.schemas import Anomaly, AnalysisResult, Hypothesis, ParsedEvent
from ..models.investigation import InvestigationReport
from .correlator import (
    build_error_bursts,
    build_timeline_segments,
    compute_service_impacts,
    extract_correlation_groups,
    group_repeated_errors,
)
from .ai_layer import ai_reason

ENGINE_VERSION = "2.0.0"


def _compute_severity_verdict(
    result: AnalysisResult,
) -> tuple[Literal["critical", "high", "medium", "low", "inconclusive"], str]:
    """Derive a severity verdict from deterministic evidence only."""
    ec = result.summary.error_count
    ac = result.summary.anomalies_flagged
    rules = {a.rule for a in result.anomalies}

    if ec == 0 and ac == 0:
        return "inconclusive", "No errors or anomalies detected in the log sample."
    if "error_spike" in rules or "retry_storm" in rules or ec >= 10:
        return "critical", (
            f"{ec} errors with {ac} anomalies including high-severity patterns "
            f"(spike/storm). Immediate investigation recommended."
        )
    if "failure_chain" in rules or ec >= 5:
        return "high", (
            f"{ec} errors with {ac} anomalies including a potential failure chain. "
            "Prompt investigation recommended."
        )
    if ac >= 1 or ec >= 2:
        return "medium", (
            f"{ec} errors, {ac} anomalies. Review flagged patterns and correlate with metrics."
        )
    return "low", f"Minimal errors ({ec}) with no strong anomaly patterns."


def _compute_incident_window(
    events: List[ParsedEvent],
) -> tuple[Optional[str], Optional[str]]:
    """Return (first_error_ts, last_error_ts) for all timestamped ERRORs."""
    error_ts = [
        e.timestamp
        for e in events
        if e.severity == "ERROR" and e.timestamp_parsed and e.timestamp
    ]
    if not error_ts:
        return None, None
    return error_ts[0], error_ts[-1]


def _compute_evidence_strength(
    result: AnalysisResult,
) -> Literal["strong", "moderate", "limited", "insufficient"]:
    ec = result.summary.error_count
    ul = result.summary.unrecognised_lines
    tl = result.summary.total_lines
    timed_errors = sum(1 for e in result.events if e.severity == "ERROR" and e.timestamp_parsed)

    if ec == 0 or (tl > 0 and ul / tl > 0.6):
        return "insufficient"
    if ec >= 5 and timed_errors >= 4 and len(result.anomalies) >= 2:
        return "strong"
    if ec >= 2 and timed_errors >= 2:
        return "moderate"
    return "limited"


def _compute_root_cause_status(
    result: AnalysisResult,
    verdict: str,
) -> Literal["confirmed", "probable", "possible", "undetermined"]:
    if verdict == "inconclusive" or result.summary.error_count == 0:
        return "undetermined"
    rules = {a.rule for a in result.anomalies}
    if "failure_chain" in rules or "retry_storm" in rules:
        return "probable"
    if result.anomalies:
        return "possible"
    return "undetermined"


def build_investigation_report(
    result: AnalysisResult,
    use_ai: bool = False,
) -> InvestigationReport:
    """Build a complete InvestigationReport from an AnalysisResult.

    Parameters
    ----------
    result:
        The output of AnalysisEngine.analyze(). Never mutated.
    use_ai:
        When True, the optional AI reasoning layer is attempted (with
        deterministic fallback on any failure). When False (default), the
        deterministic fallback provider is used unconditionally — no external
        API is called.
    """
    events = result.events
    anomalies = result.anomalies
    hypotheses = result.hypotheses

    # --- Correlation layer (pure deterministic) ---
    timeline_segments = build_timeline_segments(events)
    error_bursts = build_error_bursts(events)
    repeated_groups = group_repeated_errors(events)
    corr_id_groups = extract_correlation_groups(events)
    service_impacts_models = compute_service_impacts(events)
    service_impacts_dicts = [s.model_dump() for s in service_impacts_models]

    # --- Severity verdict & evidence semantics ---
    verdict, rationale = _compute_severity_verdict(result)
    incident_start, incident_end = _compute_incident_window(events)
    evidence_strength = _compute_evidence_strength(result)
    root_cause_status = _compute_root_cause_status(result, verdict)

    # Determine mode
    mode: Literal["deterministic", "ai_assisted"] = "ai_assisted" if use_ai else "deterministic"

    # Build a partial report (needed by ai_reason for context)
    partial = InvestigationReport(
        filename=result.filename,
        engine_version=ENGINE_VERSION,
        analysis_mode=mode,
        incident_start=incident_start,
        incident_end=incident_end,
        severity_verdict=verdict,
        severity_rationale=rationale,
        evidence_strength=evidence_strength,
        root_cause_status=root_cause_status,
        analysis_method="rules_based",
        timeline_segments=timeline_segments,
        error_bursts=error_bursts,
        repeated_error_groups=repeated_groups,
        correlation_id_groups=corr_id_groups,
        service_impacts=service_impacts_models,
    )

    # --- Optional AI layer ---
    ai_reasoning, ai_attempted, ai_failure = ai_reason(
        events=events,
        anomalies=anomalies,
        hypotheses=hypotheses,
        summary=result.summary.model_dump(),
        service_impacts=service_impacts_dicts,
        report=partial,
        use_ai=use_ai,
    )

    method: Literal["rules_based", "ai_assisted", "backup_method"]
    if ai_attempted and not ai_failure:
        method = "ai_assisted"
    elif ai_attempted and ai_failure:
        method = "backup_method"
    else:
        method = "rules_based"

    return InvestigationReport(
        filename=result.filename,
        engine_version=ENGINE_VERSION,
        analysis_mode="ai_assisted" if (ai_attempted and not ai_failure) else "deterministic",
        incident_start=incident_start,
        incident_end=incident_end,
        severity_verdict=verdict,
        severity_rationale=rationale,
        evidence_strength=evidence_strength,
        root_cause_status=root_cause_status,
        analysis_method=method,
        timeline_segments=timeline_segments,
        error_bursts=error_bursts,
        repeated_error_groups=repeated_groups,
        correlation_id_groups=corr_id_groups,
        service_impacts=service_impacts_models,
        ai_reasoning=ai_reasoning,
        ai_was_attempted=ai_attempted,
        ai_failure_reason=ai_failure,
    )
