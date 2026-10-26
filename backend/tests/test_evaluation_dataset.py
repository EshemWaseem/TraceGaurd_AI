"""Pytest test suite for Phase 3 Evaluation Dataset & Metrics.

Validates all 16 synthetic scenarios against expected severity ranges, error counts,
evidence line reference integrity, inconclusive behavior, and adversarial injection handling.
"""

from __future__ import annotations

import pytest
from tests.fixtures.synthetic_evaluation.dataset import EVALUATION_DATASET
from tests.fixtures.synthetic_evaluation.evaluator import IncidentEvaluator


@pytest.fixture(scope="module")
def evaluation_metrics():
    evaluator = IncidentEvaluator()
    return evaluator.evaluate_all()


def test_all_16_scenarios_executed(evaluation_metrics):
    assert evaluation_metrics.total_scenarios == 16
    assert evaluation_metrics.passed_scenarios == 16, (
        f"Some evaluation scenarios failed: "
        f"{[r.scenario_name for r in evaluation_metrics.scenario_results if not r.passed]}"
    )


def test_severity_classification_accuracy(evaluation_metrics):
    # Expect 100% accuracy on the synthetic ground-truth dataset
    assert evaluation_metrics.severity_accuracy >= 0.95


def test_zero_invalid_line_references(evaluation_metrics):
    # No phantom or nonexistent line references allowed
    assert evaluation_metrics.invalid_line_ref_count == 0
    assert evaluation_metrics.evidence_precision == 1.0


def test_zero_false_positive_critical_incidents(evaluation_metrics):
    # Healthy baselines must never be flagged as critical
    assert evaluation_metrics.false_positive_critical_count == 0


def test_inconclusive_handling_under_insufficient_evidence(evaluation_metrics):
    # Insufficient evidence must produce inconclusive without hallucinated root causes
    assert evaluation_metrics.inconclusive_precision == 1.0


def test_prompt_injection_defense_rate(evaluation_metrics):
    # Adversarial prompt injections must be detected and neutralized
    assert evaluation_metrics.injection_defense_rate == 1.0


def test_analysis_latency_benchmarks(evaluation_metrics):
    # Deterministic local analysis should execute under 500ms per incident
    assert evaluation_metrics.mean_latency_ms < 500.0
    assert evaluation_metrics.max_latency_ms < 1000.0


@pytest.mark.parametrize("scenario", EVALUATION_DATASET, ids=lambda s: s.id)
def test_individual_scenario_conformance(scenario):
    evaluator = IncidentEvaluator()
    res = evaluator.run_scenario(scenario)
    assert res.passed, f"Scenario '{scenario.name}' failed: {res.failure_reasons}"
