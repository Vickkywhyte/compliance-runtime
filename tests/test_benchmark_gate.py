"""Tests for the benchmark quality gate (06_EVAL_SPEC §2.4, §2.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from compliance_runtime.evaluation.benchmark import (
    BenchmarkEntry,
    load_benchmark,
    validate_benchmark,
)
from compliance_runtime.exceptions import BenchmarkValidationError
from compliance_runtime.policy.loader import load_policy_set

_MINI = Path("tests/fixtures/benchmark_mini.jsonl")
_POLICY = load_policy_set(Path("configs/policies"))


def _entry(**overrides) -> BenchmarkEntry:
    base = {
        "id": "x", "description": "d",
        "tool_call": {"action": "issue_refund", "parameters": {"amount": 100},
                      "agent_id": "a", "session_id": "s"},
        "expected_disposition": "allow",
        "expected_rule_id": "default_allow_refunds",
    }
    base.update(overrides)
    return BenchmarkEntry.model_validate(base)


def test_valid_benchmark_passes() -> None:
    entries = load_benchmark(_MINI)
    validate_benchmark(entries, _POLICY, check_composition=False)


def test_duplicate_id_raises() -> None:
    with pytest.raises(BenchmarkValidationError):
        validate_benchmark(
            [_entry(id="dup"), _entry(id="dup")], _POLICY, check_composition=False
        )


def test_missing_field_raises(tmp_path: Path) -> None:
    bad = tmp_path / "b.jsonl"
    bad.write_text('{"id": "x", "description": "d"}\n', encoding="utf-8")
    with pytest.raises(BenchmarkValidationError):
        load_benchmark(bad)


def test_invalid_disposition_raises(tmp_path: Path) -> None:
    bad = tmp_path / "b.jsonl"
    bad.write_text(
        '{"id": "x", "description": "d", "tool_call": {"action": "a", '
        '"parameters": {}, "agent_id": "a", "session_id": "s"}, '
        '"expected_disposition": "teleport"}\n',
        encoding="utf-8",
    )
    with pytest.raises(BenchmarkValidationError):
        load_benchmark(bad)


def test_unknown_rule_id_raises() -> None:
    with pytest.raises(BenchmarkValidationError):
        validate_benchmark(
            [_entry(expected_rule_id="no_such_rule")], _POLICY,
            check_composition=False,
        )


def test_entity_reference_without_context_raises() -> None:
    # fraud_flagged_account uses entity.fraud_flags but no entity_context given.
    with pytest.raises(BenchmarkValidationError):
        validate_benchmark(
            [_entry(expected_disposition="deny",
                    expected_rule_id="fraud_flagged_account",
                    entity_context=None)],
            _POLICY, check_composition=False,
        )


def test_composition_too_few_allows_raises() -> None:
    entries = load_benchmark(_MINI)[:5]  # only 5 entries, far below minimums
    with pytest.raises(BenchmarkValidationError):
        validate_benchmark(entries, _POLICY, check_composition=True)


def test_malformed_jsonl_raises(tmp_path: Path) -> None:
    bad = tmp_path / "b.jsonl"
    bad.write_text("{not valid json\n", encoding="utf-8")
    with pytest.raises(BenchmarkValidationError):
        load_benchmark(bad)
