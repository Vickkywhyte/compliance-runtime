"""Metric fixtures (06_EVAL_SPEC §9): each asserts the value within 1e-6."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from compliance_runtime.evaluation.metrics.enforcement import (
    FalseNegativeRate,
    FalsePositiveRate,
    PolicyCoverage,
    PolicyPrecision,
    PolicyRecall,
)
from compliance_runtime.evaluation.metrics.evidence import (
    AuditCompleteness,
    ChainIntegrity,
    SignatureValidity,
)
from compliance_runtime.evaluation.metrics.operational import (
    CostPer1kActionsUsd,
    RuntimeOverheadP50,
)
from compliance_runtime.evaluation.metrics.oversight import (
    ApprovalLatencyP50,
    ApprovalLatencyP95,
    ApprovalRate,
    AutoDenyRate,
    OverrideRate,
)

_CASES = json.loads(Path("tests/fixtures/metrics_cases.json").read_text(encoding="utf-8"))
_TOL = 1e-6


def _check(metric, metric_key: str, case_key: str) -> None:
    case = _CASES[metric_key][case_key]
    assert metric.compute(case["context"]) == pytest.approx(case["expected"], abs=_TOL)


def test_policy_precision_perfect() -> None:
    _check(PolicyPrecision(), "policy_precision", "perfect")


def test_policy_precision_one_fp() -> None:
    _check(PolicyPrecision(), "policy_precision", "one_fp")


def test_policy_recall_perfect() -> None:
    _check(PolicyRecall(), "policy_recall", "perfect")


def test_policy_recall_one_fn() -> None:
    _check(PolicyRecall(), "policy_recall", "one_fn")


def test_fpr_perfect_zero() -> None:
    _check(FalsePositiveRate(), "false_positive_rate", "perfect_zero")


def test_fpr_one_violation() -> None:
    _check(FalsePositiveRate(), "false_positive_rate", "one_violation")


def test_fnr_perfect_zero() -> None:
    _check(FalseNegativeRate(), "false_negative_rate", "perfect_zero")


def test_fnr_one_violation() -> None:
    _check(FalseNegativeRate(), "false_negative_rate", "one_violation")


def test_policy_coverage_perfect() -> None:
    _check(PolicyCoverage(), "policy_coverage", "perfect")


def test_policy_coverage_gap() -> None:
    _check(PolicyCoverage(), "policy_coverage", "gap")


def test_audit_completeness_full() -> None:
    _check(AuditCompleteness(), "audit_completeness", "full")


def test_audit_completeness_partial() -> None:
    _check(AuditCompleteness(), "audit_completeness", "partial")


def test_chain_integrity_all_valid() -> None:
    _check(ChainIntegrity(), "chain_integrity", "all_valid")


def test_chain_integrity_broken() -> None:
    _check(ChainIntegrity(), "chain_integrity", "broken")


def test_signature_validity_all_valid() -> None:
    _check(SignatureValidity(), "signature_validity", "all_valid")


def test_signature_validity_broken() -> None:
    _check(SignatureValidity(), "signature_validity", "broken")


def test_approval_latency_p50() -> None:
    _check(ApprovalLatencyP50(), "approval_latency_p50_ms", "case")


def test_approval_latency_p95() -> None:
    _check(ApprovalLatencyP95(), "approval_latency_p95_ms", "case")


def test_approval_rate_all_approved() -> None:
    _check(ApprovalRate(), "approval_rate", "all_approved")


def test_override_rate_with_overrides() -> None:
    _check(OverrideRate(), "override_rate", "with_overrides")


def test_auto_deny_rate_with_expirations() -> None:
    _check(AutoDenyRate(), "auto_deny_rate", "with_expirations")


def test_runtime_overhead_p50() -> None:
    _check(RuntimeOverheadP50(), "runtime_overhead_p50_ms", "case")


def test_cost_per_1k_actions_is_zero() -> None:
    _check(CostPer1kActionsUsd(), "cost_per_1k_actions_usd", "case")


def test_metric_directions() -> None:
    assert FalsePositiveRate().direction == "lower_better"
    assert FalseNegativeRate().direction == "lower_better"
    assert ApprovalLatencyP50().direction == "lower_better"
    assert PolicyPrecision().direction == "higher_better"
