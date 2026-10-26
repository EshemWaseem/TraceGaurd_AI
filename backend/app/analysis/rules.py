"""Five deterministic detection rules for TraceGuard AI.

Rule 1 — Error Spike:      ≥3 ERRORs in any 60-second window (timestamps required).
Rule 2 — Repeated Error:   ≥3 ERRORs with same normalised message.
Rule 3 — Retry Storm:      ≥2 subsequent attempts after initial error within 30 s,
                            same service AND identifiable operation required.
Rule 4 — Failure Chain:    ERROR A followed by distinct ERROR B within 120 s
                            → one anomaly (detected_pattern) + one hypothesis (unconfirmed).
Rule 5 — Unrecognised:     Collected by parsers; aggregated by engine (not a post-hoc rule).
"""

import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Optional

from ..models.schemas import Anomaly, Hypothesis, MatchedRule, ParsedEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_dt(ts: str) -> datetime:
    return datetime.fromisoformat(ts.rstrip("Z"))


def _normalise_msg(msg: str) -> str:
    """Lowercase, strip UUIDs, strip numbers, collapse whitespace."""
    msg = msg.lower()
    msg = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "", msg)
    msg = re.sub(r"\d+", "", msg)
    msg = re.sub(r"\s+", " ", msg).strip()
    return msg


def _extract_operation(message: str) -> Optional[str]:
    """Extract a stable operation identifier from a message.

    Returns None when no identifiable operation can be derived.
    Uses explicit HTTP-method+path pattern first, then colon-delimited prefix.
    """
    # HTTP request pattern: "GET /some/path …"
    m = re.match(r"^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(/[\w/._-]*)", message, re.IGNORECASE)
    if m:
        return f"{m.group(1).upper()} {m.group(2)}"
    # "operation: details" or "ExceptionClass: message"
    if ":" in message:
        prefix = message.split(":")[0].strip()
        # Reject single-word prefixes that look like log levels or noise
        if prefix and " " not in prefix and len(prefix) > 3:
            return prefix
    return None


# ---------------------------------------------------------------------------
# Rule 1 — Error Spike
# ---------------------------------------------------------------------------

def error_spike(events: List[ParsedEvent]) -> List[Anomaly]:
    """≥3 ERROR events within any 60-second sliding window (timestamps required)."""
    errors = sorted(
        [e for e in events if e.severity == "ERROR" and e.timestamp_parsed and e.timestamp],
        key=lambda e: _to_dt(e.timestamp),  # type: ignore[arg-type]
    )
    if len(errors) < 3:
        return []

    best: List[ParsedEvent] = []
    for i in range(len(errors)):
        t0 = _to_dt(errors[i].timestamp)  # type: ignore[arg-type]
        window = [errors[i]]
        for j in range(i + 1, len(errors)):
            if _to_dt(errors[j].timestamp) - t0 <= timedelta(seconds=60):  # type: ignore[arg-type]
                window.append(errors[j])
            else:
                break
        if len(window) > len(best):
            best = window

    if len(best) < 3:
        return []

    return [Anomaly(
        id="error_spike",
        rule="error_spike",
        title=f"Error spike: {len(best)} errors in 60 s",
        epistemic_label="detected_pattern",
        explanation=(
            f"{len(best)} ERROR events occurred within a 60-second window. "
            "Events without a valid timestamp are excluded from this rule."
        ),
        matched_rule=MatchedRule(
            name="Error Spike",
            description="≥3 ERROR events in a rolling 60-second window",
            threshold="3 errors / 60 s",
        ),
        evidence_line_numbers=[e.line_number for e in best],
        supporting_line_count=len(best),
    )]


# ---------------------------------------------------------------------------
# Rule 2 — Repeated Error Cluster
# ---------------------------------------------------------------------------

def repeated_error_cluster(events: List[ParsedEvent]) -> List[Anomaly]:
    """≥3 ERROR events sharing the same normalised message."""
    import hashlib
    groups: Dict[str, List[ParsedEvent]] = defaultdict(list)
    for e in events:
        if e.severity == "ERROR":
            groups[_normalise_msg(e.message)].append(e)

    anomalies: List[Anomaly] = []
    for norm, evs in groups.items():
        if len(evs) >= 3:
            h = hashlib.md5(norm.encode("utf-8")).hexdigest()[:6]
            slug = re.sub(r"[^a-z0-9]+", "_", norm[:16]).strip("_") or "cluster"
            service_label = f"[{evs[0].service}] " if evs[0].service else ""
            msg_snippet = evs[0].message[:45].strip()
            if len(evs[0].message) > 45:
                msg_snippet += "..."
            anomalies.append(Anomaly(
                id=f"repeated_error_{slug}_{h}",
                rule="repeated_error_cluster",
                title=f"Repeated error ({len(evs)}x): {service_label}'{msg_snippet}'",
                epistemic_label="detected_pattern",
                explanation=(
                    f"{len(evs)} ERROR events matched this normalised pattern. "
                    "Original messages are preserved in the evidence."
                ),
                matched_rule=MatchedRule(
                    name="Repeated Error Cluster",
                    description="≥3 ERROR events with the same normalised message",
                    threshold="3 occurrences",
                ),
                evidence_line_numbers=[e.line_number for e in evs],
                supporting_line_count=len(evs),
                relationship="main_finding",
            ))
    return anomalies


# ---------------------------------------------------------------------------
# Rule 3 — Retry Storm
# ---------------------------------------------------------------------------

def retry_storm(events: List[ParsedEvent]) -> List[Anomaly]:
    """Retry storm: initial ERROR + ≥2 subsequent attempts within 30 s.

    Requires same service AND identifiable operation. If operation cannot
    be established, falls through to repeated_error_cluster (Rule 2).
    """
    anomalies: List[Anomaly] = []
    seen_chains: set = set()

    timed = [e for e in events if e.severity == "ERROR" and e.timestamp_parsed and e.timestamp]
    timed.sort(key=lambda e: _to_dt(e.timestamp))  # type: ignore[arg-type]

    for i, ev in enumerate(timed):
        op = _extract_operation(ev.message)
        if not op or not ev.service:
            # Cannot establish operation context — skip (Rule 2 will handle clustering)
            continue

        svc = ev.service
        t0 = _to_dt(ev.timestamp)  # type: ignore[arg-type]
        chain_key = (svc, op)
        if chain_key in seen_chains:
            continue

        # Collect subsequent events matching same service + operation within 30 s
        subsequent: List[ParsedEvent] = []
        for j in range(i + 1, len(timed)):
            nxt = timed[j]
            if _to_dt(nxt.timestamp) - t0 > timedelta(seconds=30):  # type: ignore[arg-type]
                break
            if nxt.service == svc and _extract_operation(nxt.message) == op:
                subsequent.append(nxt)

        # Spec: ≥2 subsequent matching attempts after the initial error
        if len(subsequent) >= 2:
            seen_chains.add(chain_key)
            all_evs = [ev] + subsequent
            anomalies.append(Anomaly(
                id=f"retry_storm_{svc}_{op[:12].replace(' ', '_').replace('/', '_')}",
                rule="retry_storm",
                title=f"Retry storm: {len(all_evs)} attempts for '{op}' on '{svc}'",
                epistemic_label="detected_pattern",
                explanation=(
                    f"Service '{svc}' encountered {len(all_evs)} errors for operation '{op}' "
                    "within 30 seconds. Both service and operation context are confirmed."
                ),
                matched_rule=MatchedRule(
                    name="Retry Storm",
                    description="Initial ERROR + ≥2 subsequent attempts within 30 s (same service & operation)",
                    threshold="3 total attempts / 30 s",
                ),
                evidence_line_numbers=[e.line_number for e in all_evs],
                supporting_line_count=len(all_evs),
            ))

    return anomalies


# ---------------------------------------------------------------------------
# Rule 4 — Failure Chain
# ---------------------------------------------------------------------------

def failure_chain(events: List[ParsedEvent]) -> Tuple[List[Anomaly], List[Hypothesis]]:
    """Detect A→B distinct ERROR pairs within 120 s.

    Each unique chain type produces one anomaly (detected_pattern) and
    one hypothesis (unconfirmed_hypothesis). B must occur AFTER A.
    """
    anomalies: List[Anomaly] = []
    hypotheses: List[Hypothesis] = []

    timed = sorted(
        [e for e in events if e.severity == "ERROR" and e.timestamp_parsed and e.timestamp],
        key=lambda e: _to_dt(e.timestamp),  # type: ignore[arg-type]
    )

    seen_chain_types: set = set()

    for i, a in enumerate(timed):
        norm_a = _normalise_msg(a.message)
        for j in range(i + 1, len(timed)):
            b = timed[j]
            diff = _to_dt(b.timestamp) - _to_dt(a.timestamp)  # type: ignore[arg-type]
            if diff <= timedelta(0):
                continue  # B must be strictly after A
            if diff > timedelta(seconds=120):
                break  # events are sorted; no further B can qualify

            norm_b = _normalise_msg(b.message)
            if norm_a == norm_b:
                continue  # same normalised message — not "distinct"

            chain_type = (norm_a, norm_b)
            if chain_type in seen_chain_types:
                continue
            seen_chain_types.add(chain_type)

            anomaly_id = f"failure_chain_{abs(hash(chain_type)) % 10**8}"
            hyp_id = f"hyp_{abs(hash(chain_type)) % 10**8}"
            evidence = [a.line_number, b.line_number]

            anomalies.append(Anomaly(
                id=anomaly_id,
                rule="failure_chain",
                title="Potential failure chain",
                epistemic_label="detected_pattern",
                explanation=(
                    f"ERROR '{a.message[:80]}' (line {a.line_number}) was followed by "
                    f"distinct ERROR '{b.message[:80]}' (line {b.line_number}) within "
                    f"{int(diff.total_seconds())} seconds. Temporal order does not confirm causation."
                ),
                matched_rule=MatchedRule(
                    name="Failure Chain",
                    description="Distinct ERROR A followed by distinct ERROR B within 120 s",
                    threshold="pair within 120 s",
                ),
                evidence_line_numbers=evidence,
                supporting_line_count=len(evidence),
            ))

            hypotheses.append(Hypothesis(
                id=hyp_id,
                title="Possible causal failure chain (unconfirmed)",
                epistemic_label="unconfirmed_hypothesis",
                plausibility="medium",
                supporting_anomaly_ids=[anomaly_id],
                evidence_line_numbers=evidence,
                next_steps=[
                    "Verify whether error A directly caused error B or both share a common root cause.",
                    "Check metrics and traces for the same time window.",
                    "Search logs for the service or component mentioned in error A.",
                ],
                llm_explanation=None,
            ))
            break  # one hypothesis per A event is sufficient

    return anomalies, hypotheses


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def apply_all_rules(
    events: List[ParsedEvent],
) -> Tuple[List[Anomaly], List[Hypothesis]]:
    raw_anomalies: List[Anomaly] = []
    hypotheses: List[Hypothesis] = []

    raw_anomalies.extend(error_spike(events))
    raw_anomalies.extend(repeated_error_cluster(events))
    raw_anomalies.extend(retry_storm(events))
    chain_anoms, chain_hyps = failure_chain(events)
    raw_anomalies.extend(chain_anoms)
    hypotheses.extend(chain_hyps)

    # Classify relationship (main_finding vs related_evidence vs additional_pattern)
    # to clarify overlapping evidence without hiding individual rules
    anomalies: List[Anomaly] = []
    seen_evidence_sets: List[set[int]] = []

    for a in raw_anomalies:
        a_ev_set = set(a.evidence_line_numbers)
        identical_match = any(a_ev_set == existing for existing in seen_evidence_sets)
        subset_match = any(a_ev_set.issubset(existing) for existing in seen_evidence_sets)

        if identical_match:
            rel = "related_evidence"
            explanation = a.explanation + " (Shares evidence lines with related pattern)."
        elif subset_match:
            rel = "related_evidence"
            explanation = a.explanation + " (Related to broader detected pattern)."
        elif len(seen_evidence_sets) >= 2:
            rel = "additional_pattern"
            explanation = a.explanation
        else:
            rel = "main_finding"
            explanation = a.explanation

        seen_evidence_sets.append(a_ev_set)
        anomalies.append(Anomaly(
            id=a.id,
            rule=a.rule,
            title=a.title,
            epistemic_label=a.epistemic_label,
            explanation=explanation,
            matched_rule=a.matched_rule,
            evidence_line_numbers=a.evidence_line_numbers,
            supporting_line_count=a.supporting_line_count,
            relationship=rel,
        ))

    return anomalies, hypotheses
