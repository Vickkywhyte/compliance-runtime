"""Metric registry for the evaluation harness (06_EVAL_SPEC §3–§6)."""

from __future__ import annotations

from compliance_runtime.evaluation.metrics.base import Metric
from compliance_runtime.evaluation.metrics.enforcement import ENFORCEMENT_METRICS
from compliance_runtime.evaluation.metrics.evidence import EVIDENCE_METRICS
from compliance_runtime.evaluation.metrics.operational import OPERATIONAL_METRICS
from compliance_runtime.evaluation.metrics.oversight import OVERSIGHT_METRICS

# Metrics for which a bootstrap CI over a well-defined per-entry mean is
# meaningful (06_EVAL_SPEC §8). The four per-entry-mean metrics are computed
# over benchmark entries; the three oversight rates are computed over approval
# requests created during the run.
CI_METRIC_NAMES = frozenset(
    {
        "policy_coverage",
        "audit_completeness",
        "chain_integrity",
        "signature_validity",
        "approval_rate",
        "override_rate",
        "auto_deny_rate",
    }
)


def all_metrics() -> list[Metric]:
    """Return every metric instance, grouped enforcement→evidence→oversight→op."""
    return [
        *ENFORCEMENT_METRICS,
        *EVIDENCE_METRICS,
        *OVERSIGHT_METRICS,
        *OPERATIONAL_METRICS,
    ]


def metric_names() -> list[str]:
    """Return the names of every metric, in registry order."""
    return [m.name for m in all_metrics()]


def _self_test() -> None:
    """Confirm the registry covers every §3–§6 metric with unique names."""
    names = metric_names()
    assert len(names) == len(set(names)), "duplicate metric names"
    expected = {
        "policy_precision", "policy_recall", "false_positive_rate",
        "false_negative_rate", "policy_coverage", "audit_completeness",
        "chain_integrity", "signature_validity", "approval_latency_p50_ms",
        "approval_latency_p95_ms", "approval_rate", "override_rate",
        "auto_deny_rate", "runtime_overhead_p50_ms", "policy_eval_p50_ms",
        "evidence_write_p50_ms", "cost_per_1k_actions_usd",
    }
    assert set(names) == expected, set(names) ^ expected
    print("evaluation.metrics self-test: PASS")


if __name__ == "__main__":
    _self_test()
