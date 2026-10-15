"""Tests for semantic policy validation (C-28, C-31)."""

from __future__ import annotations

import pytest

from compliance_runtime.exceptions import PolicyValidationError
from compliance_runtime.policy.models import (
    Policy,
    PolicyCondition,
    PolicyEnforcement,
    PolicyRule,
)
from compliance_runtime.policy.validators import validate_policy


_UNSET: object = object()


def _rule(
    rule_id: str = "r1",
    priority: int = 10,
    when: object = _UNSET,
    enforce: PolicyEnforcement | None = None,
) -> PolicyRule:
    if when is _UNSET:
        when = [PolicyCondition(field="action", operator="equals", value="x")]
    return PolicyRule(
        id=rule_id,
        priority=priority,
        description="d",
        when=when,  # type: ignore[arg-type]
        enforce=enforce or PolicyEnforcement(disposition="allow", reason="ok"),
    )


def _policy(rules: list[PolicyRule]) -> Policy:
    return Policy(name="p", version="1.0.0", rules=rules)


def test_valid_policy_passes() -> None:
    validate_policy(_policy([_rule()]))


def test_duplicate_rule_ids_raise() -> None:
    with pytest.raises(PolicyValidationError):
        validate_policy(_policy([_rule("dup", 10), _rule("dup", 20)]))


def test_duplicate_priorities_raise() -> None:
    with pytest.raises(PolicyValidationError):
        validate_policy(_policy([_rule("a", 10), _rule("b", 10)]))


def test_invalid_field_pattern_raises() -> None:
    bad = _rule(
        when=[PolicyCondition(field="parameters.bad-name", operator="equals",
                              value=1)]
    )
    with pytest.raises(PolicyValidationError):
        validate_policy(_policy([bad]))


def test_invalid_operator_raises() -> None:
    # Bypass the Literal at construction to reach the validator's own check.
    cond = PolicyCondition.model_construct(
        field="action", operator="bogus_operator", value=1
    )
    rule = _rule(when=[cond])
    with pytest.raises(PolicyValidationError):
        validate_policy(_policy([rule]))


def test_incompatible_value_type_raises() -> None:
    bad = _rule(
        when=[PolicyCondition(field="parameters.amount",
                              operator="greater_than", value="not-a-number")]
    )
    with pytest.raises(PolicyValidationError):
        validate_policy(_policy([bad]))


def test_invalid_regex_raises() -> None:
    bad = _rule(
        when=[PolicyCondition(field="action", operator="matches_regex",
                              value="[unterminated")]
    )
    with pytest.raises(PolicyValidationError):
        validate_policy(_policy([bad]))


def test_missing_require_role_raises() -> None:
    bad = _rule(
        enforce=PolicyEnforcement(disposition="require_approval", reason="r")
    )
    with pytest.raises(PolicyValidationError):
        validate_policy(_policy([bad]))


def test_empty_when_raises() -> None:
    with pytest.raises(PolicyValidationError):
        validate_policy(_policy([_rule(when=[])]))
