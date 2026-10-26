"""Evaluation engine and metrics calculator for TraceGuard AI Phase 3.

Executes all 16 scenarios in the synthetic evaluation dataset against the
AnalysisEngine and InvestigationBuilder, verifying:
- Severity classification accuracy
- Evidence line reference precision (zero nonexistent line references)
- False-positive critical incident count (must be 0)
- Inconclusive handling under insufficient evidence
- Adversarial injection handling
- Execution latency benchmarks (mean, p95)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

from app.analysis.engine import AnalysisEngine
from app.analysis.investigation_builder import build_investigation_report
from .dataset import EVALUATION_DATASET, EvaluationScenario


@dataclass
class ScenarioResult:
    scenario_id: str
    scenario_name: str
    passed: bool
    verdict: str
    expected_verdicts: List[str]
    error_count: int
    anomalies_flagged: int
    duration_ms: float
    invalid_line_refs: List[int]
    total_line_refs: int
    injection_detected: bool
    is_inconclusive: bool
    hypothesis_present: bool
    failure_reasons: List[str] = field(default_factory=list)


@dataclass
class EvaluationMetrics:
    total_scenarios: int
    passed_scenarios: int
    severity_accuracy: float
    evidence_precision: float
    invalid_line_ref_count: int
    false_positive_critical_count: int
    inconclusive_precision: float
    injection_defense_rate: float
    mean_latency_ms: float
    max_latency_ms: float
    scenario_results: List[ScenarioResult]


class IncidentEvaluator:
    """Evaluates the investigation engine against the synthetic benchmark."""

    def __init__(self) -> None:
        self.engine = AnalysisEngine()

    def run_scenario(self, scenario: EvaluationScenario) -> ScenarioResult:
        t0 = time.perf_counter()
        analysis_result = self.engine.analyze(scenario.content, scenario.filename)
        report = build_investigation_report(analysis_result, use_ai=False)
        duration_ms = (time.perf_counter() - t0) * 1000.0

        failures: List[str] = []
        valid_lines = {e.line_number for e in analysis_result.events}

        # 1. Severity verdict check
        verdict = report.severity_verdict
        if verdict not in scenario.expected_verdicts:
            failures.append(
                f"Severity verdict '{verdict}' not in expected {scenario.expected_verdicts}"
            )

        # 2. Error count bounds
        ec = analysis_result.summary.error_count
        if not (scenario.expected_min_errors <= ec <= scenario.expected_max_errors):
            failures.append(
                f"Error count {ec} not in expected [{scenario.expected_min_errors}, {scenario.expected_max_errors}]"
            )

        # 3. Evidence line references integrity (must exist in parsed events)
        invalid_refs: List[int] = []
        total_refs = 0
        all_cited_lines: List[int] = []

        if report.ai_reasoning:
            all_cited_lines.extend(report.ai_reasoning.line_references)
        for a in analysis_result.anomalies:
            all_cited_lines.extend(a.evidence_line_numbers)
        for burst in report.error_bursts:
            all_cited_lines.extend(burst.line_numbers)
        for cluster in report.repeated_error_groups:
            all_cited_lines.extend(cluster.line_numbers)

        for ln in all_cited_lines:
            total_refs += 1
            if ln not in valid_lines:
                invalid_refs.append(ln)

        if invalid_refs:
            failures.append(f"Found invalid/nonexistent line references: {invalid_refs}")

        # 4. Inconclusive expectation
        if scenario.is_inconclusive and not scenario.allow_ai_hypothesis:
            if report.ai_reasoning and report.ai_reasoning.root_cause_hypothesis:
                failures.append(
                    f"Manufactured root cause hypothesis '{report.ai_reasoning.root_cause_hypothesis}' under insufficient evidence"
                )

        # 5. Injection expectation
        injected = report.ai_reasoning.injected_content_detected if report.ai_reasoning else False
        if scenario.injection_expected and not injected:
            failures.append("Expected prompt injection detection to trigger, but it did not.")

        # 6. False positive check on healthy baseline
        if scenario.id == "scenario_16_healthy_baseline":
            if verdict == "critical":
                failures.append("False positive critical incident on healthy baseline log.")

        passed = len(failures) == 0

        return ScenarioResult(
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            passed=passed,
            verdict=verdict,
            expected_verdicts=scenario.expected_verdicts,
            error_count=ec,
            anomalies_flagged=analysis_result.summary.anomalies_flagged,
            duration_ms=duration_ms,
            invalid_line_refs=invalid_refs,
            total_line_refs=total_refs,
            injection_detected=injected,
            is_inconclusive=scenario.is_inconclusive,
            hypothesis_present=bool(report.ai_reasoning and report.ai_reasoning.root_cause_hypothesis),
            failure_reasons=failures,
        )

    def evaluate_all(self) -> EvaluationMetrics:
        results: List[ScenarioResult] = []
        latencies: List[float] = []

        for scenario in EVALUATION_DATASET:
            res = self.run_scenario(scenario)
            results.append(res)
            latencies.append(res.duration_ms)

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        severity_correct = sum(1 for r in results if r.verdict in r.expected_verdicts)
        severity_acc = (severity_correct / total) if total > 0 else 0.0

        all_invalid_refs = sum(len(r.invalid_line_refs) for r in results)
        all_refs = sum(r.total_line_refs for r in results)
        evidence_prec = ((all_refs - all_invalid_refs) / all_refs) if all_refs > 0 else 1.0

        fp_critical = sum(
            1 for r in results
            if r.scenario_id == "scenario_16_healthy_baseline" and r.verdict in ("critical", "high")
        )

        inconclusive_scenarios = [r for r in results if r.is_inconclusive]
        inconclusive_correct = sum(
            1 for r in inconclusive_scenarios if not r.hypothesis_present
        )
        inconclusive_prec = (
            (inconclusive_correct / len(inconclusive_scenarios))
            if inconclusive_scenarios
            else 1.0
        )

        injection_scenarios = [s for s in EVALUATION_DATASET if s.injection_expected]
        injection_passed = sum(
            1 for r in results
            if r.scenario_id in [s.id for s in injection_scenarios] and r.injection_detected
        )
        injection_rate = (injection_passed / len(injection_scenarios)) if injection_scenarios else 1.0

        mean_lat = sum(latencies) / len(latencies) if latencies else 0.0
        max_lat = max(latencies) if latencies else 0.0

        return EvaluationMetrics(
            total_scenarios=total,
            passed_scenarios=passed,
            severity_accuracy=severity_acc,
            evidence_precision=evidence_prec,
            invalid_line_ref_count=all_invalid_refs,
            false_positive_critical_count=fp_critical,
            inconclusive_precision=inconclusive_prec,
            injection_defense_rate=injection_rate,
            mean_latency_ms=mean_lat,
            max_latency_ms=max_lat,
            scenario_results=results,
        )
