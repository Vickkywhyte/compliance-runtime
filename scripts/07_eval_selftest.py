#!/usr/bin/env python
"""Phase 7 evaluation self-test (Lesson 2, Lesson 3).

Runs the mini benchmark and asserts every metric is present, in a valid range,
and that our runtime's evidence metrics are perfect (chain + signatures).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from compliance_runtime.config.keys import set_keys_dir
from compliance_runtime.evaluation.metrics import metric_names
from compliance_runtime.evaluation.runner import EvaluationRunner
from compliance_runtime.interception.pipeline import build_pipeline
from compliance_runtime.policy.loader import load_policy_set

_UNIT_INTERVAL = {
    "policy_precision", "policy_recall", "false_positive_rate",
    "false_negative_rate", "policy_coverage", "audit_completeness",
    "chain_integrity", "signature_validity", "approval_rate",
    "override_rate", "auto_deny_rate",
}


def main() -> int:
    passed = 0
    with tempfile.TemporaryDirectory() as tmp:
        set_keys_dir(tmp)
        try:
            policy_set = load_policy_set(Path("configs/policies"))
            pipeline, _ = build_pipeline("configs/runtime.yaml", db_path=f"{tmp}/e.db")
            report = EvaluationRunner(pipeline, policy_set).run(
                Path("tests/fixtures/benchmark_mini.jsonl"), check_composition=False
            )
            pipeline.close()
        finally:
            set_keys_dir(None)

    metrics = report.aggregate_metrics

    for name in metric_names():
        assert name in metrics, f"missing metric {name}"
        passed += 1

    for name, value in metrics.items():
        assert isinstance(value, float), f"{name} is not a float"
        if name in _UNIT_INTERVAL:
            assert 0.0 - 1e-9 <= value <= 1.0 + 1e-9, f"{name}={value} out of [0,1]"
        else:
            assert value >= 0.0, f"{name}={value} is negative"
    passed += 1

    assert metrics["chain_integrity"] == 1.0, metrics["chain_integrity"]
    passed += 1
    assert metrics["signature_validity"] == 1.0, metrics["signature_validity"]
    passed += 1
    assert metrics["audit_completeness"] == 1.0, metrics["audit_completeness"]
    passed += 1

    print(f"PASS: all {passed} assertions passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
