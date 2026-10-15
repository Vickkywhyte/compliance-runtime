"""Tests for the evaluation runner (06_EVAL_SPEC §10)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from compliance_runtime.config.keys import set_keys_dir
from compliance_runtime.evaluation.metrics import metric_names
from compliance_runtime.evaluation.runner import EvalReport, EvaluationRunner
from compliance_runtime.interception.pipeline import build_pipeline
from compliance_runtime.policy.loader import load_policy_set

_MINI = Path("tests/fixtures/benchmark_mini.jsonl")


def _run(tmp_path: Path) -> EvalReport:
    policy_set = load_policy_set(Path("configs/policies"))
    pipeline, _ = build_pipeline("configs/runtime.yaml", db_path=tmp_path / "e.db")
    try:
        return EvaluationRunner(pipeline, policy_set, seed=0).run(
            _MINI, check_composition=False
        )
    finally:
        pipeline.close()


@pytest.fixture()
def report(tmp_path: Path) -> Iterator[EvalReport]:
    set_keys_dir(tmp_path)
    try:
        yield _run(tmp_path)
    finally:
        set_keys_dir(None)


def test_runner_produces_eval_report(report: EvalReport) -> None:
    assert isinstance(report, EvalReport)
    assert report.n_entries == 20
    assert len(report.per_entry) == 20


def test_runner_has_all_aggregate_metrics(report: EvalReport) -> None:
    for name in metric_names():
        assert name in report.aggregate_metrics


def test_runner_computes_ci(report: EvalReport) -> None:
    assert report.aggregate_ci
    for bounds in report.aggregate_ci.values():
        assert len(bounds) == 2 and bounds[0] <= bounds[1]


def test_runner_writes_json_file(tmp_path: Path) -> None:
    set_keys_dir(tmp_path)
    try:
        policy_set = load_policy_set(Path("configs/policies"))
        pipeline, _ = build_pipeline("configs/runtime.yaml", db_path=tmp_path / "e.db")
        out = tmp_path / "evals"
        report = EvaluationRunner(pipeline, policy_set).run(
            _MINI, check_composition=False, output_dir=out
        )
        pipeline.close()
        assert (out / f"{report.eval_id}.json").exists()
    finally:
        set_keys_dir(None)


def test_runner_hermetic(report: EvalReport) -> None:
    # Perfect evidence metrics prove the hermetic run signed + chained cleanly.
    assert report.aggregate_metrics["chain_integrity"] == 1.0
    assert report.aggregate_metrics["signature_validity"] == 1.0


# Wall-clock metrics are not deterministic by nature; §21 determinism covers
# disposition/evidence/rate metrics (ULIDs, timestamps, latencies may vary).
_DETERMINISTIC = {
    "policy_precision", "policy_recall", "false_positive_rate",
    "false_negative_rate", "policy_coverage", "audit_completeness",
    "chain_integrity", "signature_validity", "approval_rate", "override_rate",
    "auto_deny_rate", "cost_per_1k_actions_usd",
}


def test_runner_deterministic_metrics(tmp_path: Path) -> None:
    set_keys_dir(tmp_path)
    try:
        first = _run(tmp_path / "a")
        second = _run(tmp_path / "b")
    finally:
        set_keys_dir(None)
    for name in _DETERMINISTIC:
        assert first.aggregate_metrics[name] == second.aggregate_metrics[name], name
