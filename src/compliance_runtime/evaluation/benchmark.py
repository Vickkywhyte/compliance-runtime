"""Benchmark loader + quality gate (06_EVAL_SPEC §2, Lesson 4).

Structural validation (§2.4) always runs; composition validation (§2.2, the
≥80/60/40/20 minimums) is opt-in via ``check_composition`` so smaller fixtures
can be used in tests without meeting the production minimums.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from compliance_runtime.exceptions import BenchmarkValidationError
from compliance_runtime.policy.models import PolicySet
from compliance_runtime.storage.models import Disposition

# Minimum entries per expected disposition for a production benchmark (§2.2).
_COMPOSITION_MINIMUMS: dict[str, int] = {
    "allow": 80,
    "deny": 60,
    "require_approval": 40,
    "allow_with_flag": 20,
}


class BenchmarkToolCall(BaseModel):
    """The tool call portion of a benchmark entry (§2.1)."""

    model_config = ConfigDict(extra="ignore")

    action: str
    parameters: dict[str, Any]
    agent_id: str
    session_id: str


class BenchmarkEntry(BaseModel):
    """One labeled benchmark case (§2.1)."""

    model_config = ConfigDict(extra="ignore")

    id: str
    description: str
    tool_call: BenchmarkToolCall
    entity_context: dict[str, Any] | None = None
    expected_disposition: Disposition
    expected_rule_id: str | None = None
    expected_assignee_role: str | None = None
    notes: str | None = None
    annotator: str = "claude_code"


def load_benchmark(path: Path) -> list[BenchmarkEntry]:
    """Parse a JSONL benchmark file into validated :class:`BenchmarkEntry` rows."""
    if not Path(path).exists():
        raise BenchmarkValidationError(f"Benchmark file not found: {path}")

    entries: list[BenchmarkEntry] = []
    for lineno, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BenchmarkValidationError(
                f"malformed JSON on line {lineno}: {exc}"
            ) from exc
        try:
            entries.append(BenchmarkEntry.model_validate(raw))
        except ValidationError as exc:
            raise BenchmarkValidationError(
                f"invalid benchmark entry on line {lineno}: {exc}"
            ) from exc
    return entries


def _rules_using_entity(policy_set: PolicySet) -> dict[str, bool]:
    """Map rule id → whether it references any ``entity.*`` field."""
    uses_entity: dict[str, bool] = {}
    for policy in policy_set.policies:
        for rule in policy.rules:
            uses_entity[rule.id] = any(
                cond.field.startswith("entity.") for cond in rule.when
            )
    return uses_entity


def validate_benchmark(
    entries: list[BenchmarkEntry],
    policy_set: PolicySet | None = None,
    check_composition: bool = True,
) -> None:
    """Run the quality gate (§2.4 structural, §2.2 composition).

    Raises :class:`BenchmarkValidationError` on any violation.
    """
    if not entries:
        raise BenchmarkValidationError("benchmark is empty")

    # Duplicate IDs.
    id_counts = Counter(e.id for e in entries)
    dups = [eid for eid, n in id_counts.items() if n > 1]
    if dups:
        raise BenchmarkValidationError(f"duplicate benchmark ids: {sorted(dups)}")

    rule_ids: set[str] = set()
    uses_entity: dict[str, bool] = {}
    if policy_set is not None:
        uses_entity = _rules_using_entity(policy_set)
        rule_ids = set(uses_entity)

    for entry in entries:
        # Unknown rule reference (§2.4).
        if entry.expected_rule_id is not None and policy_set is not None:
            if entry.expected_rule_id not in rule_ids:
                raise BenchmarkValidationError(
                    f"entry {entry.id!r} references unknown rule "
                    f"{entry.expected_rule_id!r}"
                )
            # entity.* rule without entity_context (§2.4).
            if uses_entity.get(entry.expected_rule_id) and entry.entity_context is None:
                raise BenchmarkValidationError(
                    f"entry {entry.id!r} maps to rule "
                    f"{entry.expected_rule_id!r} which uses entity.* but has no "
                    "entity_context"
                )

    if check_composition:
        counts = Counter(e.expected_disposition for e in entries)
        for disposition, minimum in _COMPOSITION_MINIMUMS.items():
            if counts.get(disposition, 0) < minimum:
                raise BenchmarkValidationError(
                    f"composition: need >= {minimum} {disposition!r} entries, "
                    f"got {counts.get(disposition, 0)}"
                )


def _self_test() -> None:
    """Load the mini benchmark (structural only) and confirm it is valid."""
    from compliance_runtime.policy.loader import load_policy_set

    policy_set = load_policy_set(Path("configs/policies"))
    entries = load_benchmark(Path("tests/fixtures/benchmark_mini.jsonl"))
    validate_benchmark(entries, policy_set, check_composition=False)
    assert len(entries) == 20, len(entries)
    print("evaluation.benchmark self-test: PASS")


if __name__ == "__main__":
    _self_test()
