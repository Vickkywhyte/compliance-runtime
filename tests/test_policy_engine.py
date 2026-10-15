"""Tests for the policy engine (ADR-005, ADR-006, ADR-013, ADR-014)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from compliance_runtime.policy.engine import PolicyEngine
from compliance_runtime.policy.loader import load_policy_set
from compliance_runtime.policy.models import (
    Policy,
    PolicyCondition,
    PolicyEnforcement,
    PolicyRule,
    PolicySet,
)
from compliance_runtime.storage.models import ToolCall
from compliance_runtime.utils.ids import new_ulid, now_utc

_DEMO = load_policy_set(Path("configs/policies"))


def _call(amount: Any = 100, action: str = "issue_refund") -> ToolCall:
    return ToolCall(
        call_id=new_ulid(),
        correlation_id=new_ulid(),
        agent_id="agent-1",
        session_id="sess-1",
        action=action,
        parameters={"amount": amount},
        received_at=now_utc(),
    )


def _engine(rules: list[PolicyRule]) -> PolicyEngine:
    policy = Policy(name="t", version="1.0.0", rules=rules)
    ps = PolicySet(policies=[policy], version="t@1.0.0+0", content_hash="0" * 64)
    return PolicyEngine(ps)


def _match_all_rule(rule_id: str, priority: int, disposition: str) -> PolicyRule:
    return PolicyRule(
        id=rule_id,
        priority=priority,
        description="d",
        when=[PolicyCondition(field="action", operator="equals",
                              value="issue_refund")],
        enforce=PolicyEnforcement(disposition=disposition, reason=rule_id,
                                  require_role="compliance_officer"
                                  if disposition == "require_approval" else None),
    )


def test_first_matching_rule_wins() -> None:
    engine = _engine(
        [_match_all_rule("low", 5, "deny"), _match_all_rule("high", 10, "allow")]
    )
    result = engine.evaluate(_call())
    assert result.matched_rule_id == "low"
    assert result.disposition == "deny"


def test_priority_order_ascending() -> None:
    # Declared out of order; priority 5 must be evaluated before 10.
    engine = _engine(
        [_match_all_rule("p10", 10, "allow"), _match_all_rule("p5", 5, "deny")]
    )
    assert engine.evaluate(_call()).matched_rule_id == "p5"


def test_no_matching_rule_returns_default() -> None:
    engine = PolicyEngine(_DEMO)
    result = engine.evaluate(_call(action="unknown_action"))
    assert result.matched_rule_id is None
    assert result.disposition == "allow_with_flag"


def test_fraud_flagged_account_denies() -> None:
    engine = PolicyEngine(_DEMO)
    result = engine.evaluate(
        _call(100), entity_context={"fraud_flags": ["chargeback"]}
    )
    assert result.disposition == "deny"
    assert result.matched_rule_id == "fraud_flagged_account"


def test_refund_over_limit_requires_approval() -> None:
    result = PolicyEngine(_DEMO).evaluate(_call(750))
    assert result.disposition == "require_approval"
    assert result.matched_rule_id == "refund_limit"


def test_refund_under_limit_allows() -> None:
    result = PolicyEngine(_DEMO).evaluate(_call(100))
    assert result.disposition == "allow"
    assert result.matched_rule_id == "default_allow_refunds"


def test_evaluation_records_duration() -> None:
    result = PolicyEngine(_DEMO).evaluate(_call(100))
    assert isinstance(result.evaluation_duration_ms, int)
    assert result.evaluation_duration_ms >= 0


def test_evaluation_records_policy_version() -> None:
    result = PolicyEngine(_DEMO).evaluate(_call(100))
    assert result.policy_version == _DEMO.version


def test_evaluation_deterministic() -> None:
    engine = PolicyEngine(_DEMO)
    call = _call(750)
    first = engine.evaluate(call)
    second = engine.evaluate(call)
    assert first.disposition == second.disposition
    assert first.matched_rule_id == second.matched_rule_id
    assert first.evidence == second.evidence


def test_missing_field_is_false_not_error() -> None:
    engine = PolicyEngine(_DEMO)
    call = ToolCall(
        call_id=new_ulid(),
        correlation_id=new_ulid(),
        agent_id="a",
        session_id="s",
        action="issue_refund",
        parameters={},  # no amount
        received_at=now_utc(),
    )
    result = engine.evaluate(call)
    # Neither refund rule matches (amount missing); default applies.
    assert result.matched_rule_id is None
    assert result.disposition == "allow_with_flag"


def test_string_number_coercion() -> None:
    engine = PolicyEngine(_DEMO)
    assert engine.evaluate(_call("750")).disposition == "require_approval"
    assert engine.evaluate(_call("100")).disposition == "allow"
