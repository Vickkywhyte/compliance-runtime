"""The policy evaluation engine (ADR-005, ADR-006, ADR-013, ADR-014).

:meth:`PolicyEngine.evaluate` is deterministic with respect to its inputs
(apart from the explicitly-passed rate limiter state): the same tool call
and entity context always yield the same disposition, matched rule, reason,
and evidence. No LLM is consulted (ADR-013).

Pipeline (09_RUNTIME_DESIGN §2):
1. rate limit (C-32) → deny on exceed
2. injection filter (C-08) → deny on marker
3. rules in ascending priority; first all-true rule wins
4. otherwise the configured default disposition
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Any

from compliance_runtime.policy.field_resolver import resolve_field
from compliance_runtime.policy.injection import scan_parameters
from compliance_runtime.policy.models import (
    EvaluationResult,
    PolicyCondition,
    PolicyRule,
    PolicySet,
)
from compliance_runtime.policy.rate_limit import RateLimiter
from compliance_runtime.policy.validators import validate_policy
from compliance_runtime.storage.models import Disposition
from compliance_runtime.utils.ids import now_utc

_DEFAULT_DISPOSITION: Disposition = "allow_with_flag"


def _to_number(value: Any) -> float | None:
    """Coerce numbers and numeric strings to float; never coerce bool."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _to_date(value: Any) -> datetime | None:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _compare_ordered(field_value: Any, value: Any, op: str) -> bool:
    """Apply an ordered operator with numeric-then-date coercion."""
    left_n, right_n = _to_number(field_value), _to_number(value)
    if left_n is not None and right_n is not None:
        left: Any = left_n
        right: Any = right_n
    else:
        left_d, right_d = _to_date(field_value), _to_date(value)
        if left_d is not None and right_d is not None:
            left, right = left_d, right_d
        else:
            return False
    if op == "greater_than":
        return left > right
    if op == "less_than":
        return left < right
    if op == "greater_or_equal":
        return left >= right
    if op == "less_or_equal":
        return left <= right
    return False


def _equals(field_value: Any, value: Any) -> bool:
    """Equality with numeric-string coercion (bools compared as-is)."""
    left_n, right_n = _to_number(field_value), _to_number(value)
    if left_n is not None and right_n is not None:
        return left_n == right_n
    return field_value == value


def _apply_operator(op: str, field_value: Any, value: Any) -> bool:
    """Apply a single operator. Never raises; returns False on mismatch."""
    if op == "equals":
        return _equals(field_value, value)
    if op == "not_equals":
        return not _equals(field_value, value)
    if op in {"greater_than", "less_than", "greater_or_equal", "less_or_equal"}:
        return _compare_ordered(field_value, value, op)
    if op == "in":
        return isinstance(value, list) and field_value in value
    if op == "not_in":
        return isinstance(value, list) and field_value not in value
    if op == "matches_regex":
        if not isinstance(value, str):
            return False
        try:
            return re.match(value, str(field_value)) is not None
        except re.error:
            return False
    return False


class PolicyEngine:
    """Evaluates tool calls against a policy set (first match wins)."""

    def __init__(
        self,
        policy_set: PolicySet,
        rate_limiter: RateLimiter | None = None,
        default_disposition: Disposition = _DEFAULT_DISPOSITION,
    ) -> None:
        # Defense in depth: re-validate every policy so a caller who builds
        # a PolicySet manually (bypassing load_policy_set) still cannot
        # start the engine with an invalid policy (C-31).
        for policy in policy_set.policies:
            validate_policy(policy)
        self._policy_set = policy_set
        self._rate_limiter = rate_limiter
        self._default_disposition = default_disposition
        # Rules flattened and sorted once, ascending priority (first wins).
        self._rules: list[PolicyRule] = sorted(
            (rule for policy in policy_set.policies for rule in policy.rules),
            key=lambda r: r.priority,
        )

    def _result(
        self,
        disposition: Disposition,
        reason: str,
        evidence: dict[str, Any],
        started: float,
        matched_rule_id: str | None = None,
        matched_rule_priority: int | None = None,
        matched_rule_enforcement: Any = None,
    ) -> EvaluationResult:
        return EvaluationResult(
            disposition=disposition,
            matched_rule_id=matched_rule_id,
            matched_rule_priority=matched_rule_priority,
            reason=reason,
            evidence=evidence,
            policy_version=self._policy_set.version,
            evaluated_at=now_utc(),
            evaluation_duration_ms=max(
                0, int((time.perf_counter() - started) * 1000)
            ),
            matched_rule_enforcement=matched_rule_enforcement,
        )

    def _rule_matches(
        self,
        rule: PolicyRule,
        tool_call: Any,
        entity_context: dict[str, Any] | None,
        rate_counters: dict[str, int],
    ) -> dict[str, Any] | None:
        """Return the matched-field evidence if ALL conditions hold, else None."""
        evidence: dict[str, Any] = {}
        for condition in rule.when:
            resolved = resolve_field(
                condition.field, tool_call, entity_context, rate_counters
            )
            # Missing field (None) → condition is False (never raises).
            if resolved is None:
                return None
            if not _apply_operator(condition.operator, resolved, condition.value):
                return None
            evidence[condition.field] = resolved
        return evidence

    def evaluate(
        self, tool_call: Any, entity_context: dict[str, Any] | None = None
    ) -> EvaluationResult:
        """Evaluate one tool call and return an :class:`EvaluationResult`."""
        started = time.perf_counter()

        # 1. Rate limit (C-32).
        if self._rate_limiter is not None:
            allowed, count = self._rate_limiter.check(
                tool_call.agent_id, tool_call.action
            )
            if not allowed:
                return self._result(
                    "deny",
                    "Rate limit exceeded",
                    {"rate.count": count, "agent_id": tool_call.agent_id},
                    started,
                )
            self._rate_limiter.record(tool_call.agent_id, tool_call.action)

        # 2. Injection filter (C-08).
        marker = scan_parameters(tool_call.parameters)
        if marker is not None:
            return self._result(
                "deny",
                f"Injection marker detected: {marker}",
                {"injection_marker": marker},
                started,
            )

        # 3. Rules in ascending priority; first all-true rule wins.
        rate_counters = self._rate_limiter.snapshot() if self._rate_limiter else {}
        for rule in self._rules:
            evidence = self._rule_matches(
                rule, tool_call, entity_context, rate_counters
            )
            if evidence is not None:
                return self._result(
                    rule.enforce.disposition,
                    rule.enforce.reason,
                    evidence,
                    started,
                    matched_rule_id=rule.id,
                    matched_rule_priority=rule.priority,
                    matched_rule_enforcement=rule.enforce,
                )

        # 4. No rule matched → default disposition.
        return self._result(
            self._default_disposition, "No matching rule", {}, started
        )


def _self_test() -> None:
    """Evaluate the demo policy's three canonical scenarios."""
    from pathlib import Path

    from compliance_runtime.policy.loader import load_policy_set
    from compliance_runtime.storage.models import ToolCall
    from compliance_runtime.utils.ids import new_ulid, now_utc as _now

    engine = PolicyEngine(load_policy_set(Path("configs/policies")))

    def call(amount: Any) -> ToolCall:
        return ToolCall(
            call_id=new_ulid(),
            correlation_id=new_ulid(),
            agent_id="agent-1",
            session_id="sess-1",
            action="issue_refund",
            parameters={"amount": amount},
            received_at=_now(),
        )

    assert engine.evaluate(call(100)).disposition == "allow"
    assert engine.evaluate(call(750)).disposition == "require_approval"
    denied = engine.evaluate(
        call(100), entity_context={"fraud_flags": ["chargeback"]}
    )
    assert denied.disposition == "deny", denied.disposition
    # Determinism.
    c = call(750)
    assert engine.evaluate(c).disposition == engine.evaluate(c).disposition
    print("policy.engine self-test: PASS")


if __name__ == "__main__":
    _self_test()
