"""Hardened, provider-independent AI reasoning layer for TraceGuard AI Phase 3.

Architecture & Security
------------------------
1. Defense in Depth:
   - User log content is treated strictly as untrusted data, never instructions.
   - Untrusted log text is sanitized of sensitive tokens and passwords before packaging.
   - Adversarial prompt-injection patterns trigger safe isolation and automatic fallback.
   - System instructions and untrusted log evidence are strictly separated.

2. Provider Abstraction:
   - `BaseAIProvider` defines the standard interface.
   - `DeterministicFallbackProvider` is always available, deterministic, and requires no API key.
   - Extensible provider registry with timeout and bounded execution.
   - Strict output validation ensures valid line references, canonical confidence,
     and bounded fields. Never hallucinates lines outside the parsed event set.

3. Evidence & Causal Integrity:
   - Distinguishes correlation from causation.
   - Retains alternative explanations when multiple failure patterns exist.
   - Insufficient evidence produces explicit inconclusive results, never manufactured root causes.
"""

from __future__ import annotations

import concurrent.futures
import logging
import os
import re
from typing import Any, Callable, Dict, List, Optional, Set

from ..models.investigation import AIReasoning, InvestigationReport
from ..models.schemas import Anomaly, Hypothesis, ParsedEvent
from .sanitizer import sanitize_evidence_package, sanitize_exception, sanitize_message

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants & Injection Defense Patterns
# ---------------------------------------------------------------------------

MAX_EVIDENCE_CHARS = 8_000  # Hard cap on evidence characters sent to AI
PROVIDER_TIMEOUT_SECONDS = 5.0  # Maximum time allowed for external provider

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a", re.IGNORECASE),
    re.compile(r"disregard\s+.{0,30}rules?", re.IGNORECASE),
    re.compile(r"system\s*prompt\s*override", re.IGNORECASE),
    re.compile(r"system\s*prompt", re.IGNORECASE),
    re.compile(r"admin(?:istrator)?\s+mode\s+enabled", re.IGNORECASE),
    re.compile(r"output\s+the\s+(?:database\s+)?(?:password|secret|key)", re.IGNORECASE),
    re.compile(r"<\|(?:im_start|im_end|system|user|assistant)\|?>", re.IGNORECASE),
    re.compile(r"\[INST\]|\[/INST\]"),  # Llama instruction markers
    re.compile(r"```system"),
]


def detect_prompt_injection(text: str) -> bool:
    """Return True if the text contains adversarial prompt-injection patterns."""
    if not text:
        return False
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False


# Backwards compatibility alias for existing Phase 2 tests
_detect_injection = detect_prompt_injection


# ---------------------------------------------------------------------------
# Provider Interface & Registry
# ---------------------------------------------------------------------------

class BaseAIProvider:
    """Base class for investigation AI providers."""

    provider_name: str = "base"

    def reason(
        self,
        evidence_package: Dict[str, Any],
        valid_line_numbers: Set[int],
    ) -> AIReasoning:
        raise NotImplementedError("Subclasses must implement reason()")


_REGISTRY: Dict[str, Callable[[], BaseAIProvider]] = {}


def register_provider(name: str, factory: Callable[[], BaseAIProvider]) -> None:
    """Register an AI reasoning provider factory."""
    _REGISTRY[name.lower().strip()] = factory


# ---------------------------------------------------------------------------
# Deterministic Fallback Provider
# ---------------------------------------------------------------------------

class DeterministicFallbackProvider(BaseAIProvider):
    """Constructs a validated AIReasoning envelope strictly from deterministic evidence.

    This provider is unconditionally available, makes no network calls,
    never leaks credentials, and returns evidence-supported conclusions.
    """

    provider_name = "deterministic_fallback"

    def reason(
        self,
        evidence_package: Dict[str, Any],
        valid_line_numbers: Set[int],
    ) -> AIReasoning:
        anomalies: List[Dict] = evidence_package.get("anomalies", [])
        hypotheses: List[Dict] = evidence_package.get("hypotheses", [])
        summary: Dict = evidence_package.get("summary", {})
        service_impacts: List[Dict] = evidence_package.get("service_impacts", [])

        error_count = summary.get("error_count", 0)
        anomaly_count = len(anomalies)
        top_service = service_impacts[0].get("service") if service_impacts else None

        # Build evidence line numbers strictly from anomalies
        evidence_lines: List[int] = []
        for a in anomalies:
            for ln in a.get("evidence_line_numbers", []):
                if ln in valid_line_numbers:
                    evidence_lines.append(ln)
        evidence_lines = sorted(set(evidence_lines))[:50]

        # 1. Evaluate evidence sufficiency & confidence
        # Insufficient evidence must produce inconclusive / low confidence
        if error_count == 0 and anomaly_count == 0:
            confidence = "inconclusive"
            plain_summary = "No errors or anomalies detected in the log sample. Telemetry indicates healthy baseline activity."
            root_cause: Optional[str] = None
        elif anomaly_count == 0 and error_count <= 2:
            confidence = "inconclusive"
            plain_summary = f"Isolated error event(s) ({error_count}) without recurring anomaly patterns. Insufficient evidence to establish root cause."
            root_cause = None
        elif anomaly_count >= 3:
            confidence = "high"
            plain_summary = f"{error_count} error events detected across {anomaly_count} distinct anomaly patterns."
            root_cause = hypotheses[0].get("title", None) if hypotheses else None
        elif anomaly_count >= 1:
            confidence = "medium"
            plain_summary = f"{error_count} error events with {anomaly_count} anomaly pattern(s) identified."
            root_cause = hypotheses[0].get("title", None) if hypotheses else None
        else:
            confidence = "low"
            plain_summary = f"{error_count} error event(s) observed without matching automated anomaly rules."
            root_cause = None

        if top_service and top_service != "__unknown__" and error_count > 0:
            plain_summary += f" Primary affected service observed: '{top_service}'."

        # Telemetry completeness adjustments
        missing_info: List[str] = []
        if summary.get("unrecognised_lines", 0) > 0:
            missing_info.append(
                f"{summary['unrecognised_lines']} unrecognised line(s) encountered. Structured JSON logging recommended."
            )
            # Downgrade high to medium if substantial unparsed lines exist
            if confidence == "high" and summary.get("unrecognised_lines", 0) > 3:
                confidence = "medium"

        if not service_impacts or all(s.get("service") == "__unknown__" for s in service_impacts):
            missing_info.append("Service identity missing from log entries. Add a canonical 'service' field.")
            if confidence == "high":
                confidence = "medium"

        # 2. Extract alternative explanations (preserve multiple hypotheses)
        alt_explanations: List[str] = []
        if len(hypotheses) > 1:
            for h in hypotheses[1:4]:
                t = h.get("title", "")
                if t and t not in alt_explanations:
                    alt_explanations.append(t[:200])

        if len(anomalies) > 1 and len(alt_explanations) < 2:
            for a in anomalies[1:3]:
                desc = f"Pattern '{a.get('rule')}': {a.get('title')}"
                if desc not in alt_explanations:
                    alt_explanations.append(desc[:200])

        # 3. Actionable next steps
        next_steps: List[str] = []
        for h in hypotheses[:2]:
            for step in h.get("next_steps", []):
                if step not in next_steps and len(next_steps) < 5:
                    next_steps.append(step)

        if not next_steps:
            if confidence == "inconclusive":
                next_steps = [
                    "Continue monitoring services for recurring failure indicators.",
                    "Ensure distributed tracing and structured log levels are active.",
                ]
            else:
                next_steps = [
                    "Inspect line references highlighted in the Evidence Inspector.",
                    "Verify downstream dependencies and connection pool metrics.",
                    "Correlate failure timestamps with deployment or infrastructure events.",
                ]

        return AIReasoning(
            provider=self.provider_name,
            model=None,
            summary=plain_summary[:500],
            root_cause_hypothesis=root_cause[:300] if root_cause else None,
            confidence=confidence,  # type: ignore[arg-type]
            alternative_explanations=alt_explanations[:3],
            recommended_next_steps=next_steps[:5],
            missing_information=missing_info[:5],
            line_references=evidence_lines,
            injected_content_detected=False,
        )


# Register default provider
register_provider("deterministic", lambda: DeterministicFallbackProvider())
register_provider("deterministic_fallback", lambda: DeterministicFallbackProvider())
register_provider("none", lambda: DeterministicFallbackProvider())


# ---------------------------------------------------------------------------
# Provider Validation & Execution Helper
# ---------------------------------------------------------------------------

def _validate_ai_reasoning(
    raw: Any,
    provider_name: str,
    valid_line_numbers: Set[int],
) -> AIReasoning:
    """Validate and sanitize AI provider output against the schema."""
    if isinstance(raw, AIReasoning):
        reasoning = raw
    elif isinstance(raw, dict):
        # Validate confidence enum
        conf = str(raw.get("confidence", "inconclusive")).lower()
        if conf not in ("high", "medium", "low", "inconclusive"):
            conf = "inconclusive"
        raw["confidence"] = conf
        reasoning = AIReasoning(**raw)
    else:
        raise TypeError(f"Provider returned invalid type: {type(raw)}")

    # Enforce line number existence in parsed events (zero phantom citations)
    safe_lines = [ln for ln in reasoning.line_references if ln in valid_line_numbers]

    # Sanitize any potentially reflected text
    return reasoning.model_copy(
        update={
            "provider": provider_name,
            "summary": sanitize_message(reasoning.summary)[:500],
            "root_cause_hypothesis": sanitize_message(reasoning.root_cause_hypothesis)[:300]
            if reasoning.root_cause_hypothesis
            else None,
            "alternative_explanations": [
                sanitize_message(alt)[:200] for alt in reasoning.alternative_explanations[:3]
            ],
            "recommended_next_steps": [
                sanitize_message(s)[:200] for s in reasoning.recommended_next_steps[:5]
            ],
            "missing_information": [
                sanitize_message(m)[:200] for m in reasoning.missing_information[:5]
            ],
            "line_references": safe_lines,
        }
    )


def execute_with_timeout(
    func: Callable[[], AIReasoning],
    timeout_seconds: float = PROVIDER_TIMEOUT_SECONDS,
) -> AIReasoning:
    """Execute a provider callable with a strict timeout without blocking threadpool shutdown."""
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(func)
        return future.result(timeout=timeout_seconds)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


# ---------------------------------------------------------------------------
# Public Entry Point
# ---------------------------------------------------------------------------

def ai_reason(
    events: List[ParsedEvent],
    anomalies: List[Anomaly],
    hypotheses: List[Hypothesis],
    summary: Dict,
    service_impacts: List[Dict],
    report: "InvestigationReport",
    use_ai: Optional[bool] = None,
) -> tuple[AIReasoning, bool, Optional[str]]:
    """Attempt AI reasoning; fall back to deterministic on any failure or injection.

    Returns:
        (reasoning, ai_was_attempted, failure_reason)
    """
    valid_line_numbers: Set[int] = {e.line_number for e in events}
    provider_name = os.environ.get("AI_PROVIDER", "deterministic").lower().strip()

    # 1. Build bounded evidence text
    evidence_lines: List[str] = []
    for e in events:
        if e.severity in ("ERROR", "WARN"):
            line_str = f"[L#{e.line_number}] [{e.severity}] {e.service or 'unknown'}: {e.message}"
            evidence_lines.append(line_str)

    raw_evidence_text = "\n".join(evidence_lines)[:MAX_EVIDENCE_CHARS]

    # 2. Prompt injection defense
    if detect_prompt_injection(raw_evidence_text):
        logger.warning("Adversarial prompt injection pattern detected in log input. Reverting to deterministic verification.")
        fb = DeterministicFallbackProvider()
        safe_package = {
            "summary": summary,
            "anomalies": [a.model_dump() for a in anomalies],
            "hypotheses": [h.model_dump() for h in hypotheses],
            "service_impacts": service_impacts,
            "evidence_text": sanitize_message(raw_evidence_text),
        }
        res = fb.reason(safe_package, valid_line_numbers)
        res = res.model_copy(update={"injected_content_detected": True})
        return res, False, "prompt_injection_detected"

    # 3. Sanitize evidence package before dispatch
    sanitized_package = sanitize_evidence_package({
        "summary": summary,
        "anomalies": [a.model_dump() for a in anomalies],
        "hypotheses": [h.model_dump() for h in hypotheses],
        "service_impacts": service_impacts,
        "evidence_text": raw_evidence_text,
    })

    # 4. If deterministic provider configured or explicitly disabled, use deterministic fallback
    if provider_name in ("deterministic", "deterministic_fallback", "none", "") or use_ai is False:
        fb = DeterministicFallbackProvider()
        return fb.reason(sanitized_package, valid_line_numbers), False, None

    # 5. Live / registered external provider attempt with timeout
    if provider_name not in _REGISTRY:
        logger.warning(f"Unknown AI provider '{provider_name}'. Using deterministic fallback.")
        fb = DeterministicFallbackProvider()
        return fb.reason(sanitized_package, valid_line_numbers), True, f"unknown_provider_{provider_name}"

    try:
        provider_factory = _REGISTRY[provider_name]
        provider = provider_factory()

        raw_reasoning = execute_with_timeout(
            lambda: provider.reason(sanitized_package, valid_line_numbers),
            timeout_seconds=PROVIDER_TIMEOUT_SECONDS,
        )
        validated = _validate_ai_reasoning(raw_reasoning, provider_name, valid_line_numbers)
        return validated, True, None

    except concurrent.futures.TimeoutError:
        logger.warning(f"AI Provider '{provider_name}' timed out after {PROVIDER_TIMEOUT_SECONDS}s. Falling back to deterministic.")
        fb = DeterministicFallbackProvider()
        return fb.reason(sanitized_package, valid_line_numbers), True, "provider_timeout"

    except Exception as exc:
        sanitized_err = sanitize_exception(exc)
        logger.warning(f"AI Provider '{provider_name}' failed: {sanitized_err}. Falling back to deterministic.")
        fb = DeterministicFallbackProvider()
        return fb.reason(sanitized_package, valid_line_numbers), True, sanitized_err
