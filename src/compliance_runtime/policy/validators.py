"""Semantic policy validation (C-28, C-31, 05_DATA_SPEC §9).

Structural validity (field presence, enum membership) is enforced by the
Pydantic models at load time. This module adds the cross-field and
value-compatibility rules that cannot be expressed in the schema. Any
violation raises :class:`PolicyValidationError`; the runtime refuses to
start on failure (C-31).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, get_args

from compliance_runtime.exceptions import PolicyValidationError
from compliance_runtime.policy.models import Policy, PolicyCondition
from compliance_runtime.storage.models import Disposition, Operator

_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

_VALID_OPERATORS = frozenset(get_args(Operator))
_VALID_DISPOSITIONS = frozenset(get_args(Disposition))

_NUMERIC_OPERATORS = frozenset(
    {"greater_than", "less_than", "greater_or_equal", "less_or_equal"}
)
_LIST_OPERATORS = frozenset({"in", "not_in"})


def _is_iso_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value)
        return True
    except ValueError:
        return False


def _field_is_allowed(field: str) -> bool:
    """Return True if ``field`` matches an allowed pattern (05_DATA_SPEC §9)."""
    if field in {"action", "agent_id", "session_id", "timestamp.hour"}:
        return True
    if field.startswith("parameters."):
        return bool(_NAME_RE.match(field[len("parameters.") :]))
    if field.startswith("entity."):
        return bool(_NAME_RE.match(field[len("entity.") :]))
    if field.startswith("rate.") and field.endswith("_per_minute"):
        action = field[len("rate.") : -len("_per_minute")]
        return bool(_NAME_RE.match(action))
    return False


def _validate_condition(condition: PolicyCondition, rule_id: str) -> None:
    field = condition.field
    operator = condition.operator
    value = condition.value

    if not _field_is_allowed(field):
        raise PolicyValidationError(
            f"rule {rule_id!r}: field {field!r} is not an allowed field pattern"
        )
    if operator not in _VALID_OPERATORS:
        raise PolicyValidationError(
            f"rule {rule_id!r}: operator {operator!r} is not in the operator set"
        )

    if operator in _NUMERIC_OPERATORS:
        numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
        if not (numeric or _is_iso_date(value)):
            raise PolicyValidationError(
                f"rule {rule_id!r}: operator {operator!r} requires a numeric or "
                f"ISO-date value, got {type(value).__name__}"
            )
    elif operator in _LIST_OPERATORS:
        if not isinstance(value, list):
            raise PolicyValidationError(
                f"rule {rule_id!r}: operator {operator!r} requires a list value"
            )
    elif operator == "matches_regex":
        if not isinstance(value, str):
            raise PolicyValidationError(
                f"rule {rule_id!r}: matches_regex requires a string pattern"
            )
        try:
            re.compile(value)
        except re.error as exc:
            raise PolicyValidationError(
                f"rule {rule_id!r}: invalid regex {value!r}: {exc}"
            ) from exc


def validate_policy(policy: Policy) -> None:
    """Validate a policy's semantics. Raises PolicyValidationError on failure."""
    seen_ids: set[str] = set()
    seen_priorities: set[int] = set()

    for rule in policy.rules:
        if rule.id in seen_ids:
            raise PolicyValidationError(f"duplicate rule id: {rule.id!r}")
        seen_ids.add(rule.id)

        if rule.priority in seen_priorities:
            raise PolicyValidationError(
                f"duplicate priority {rule.priority} in policy {policy.name!r}"
            )
        seen_priorities.add(rule.priority)

        if not rule.when:
            raise PolicyValidationError(
                f"rule {rule.id!r}: 'when' must have at least one condition"
            )

        for condition in rule.when:
            _validate_condition(condition, rule.id)

        enforce = rule.enforce
        if enforce.disposition not in _VALID_DISPOSITIONS:
            raise PolicyValidationError(
                f"rule {rule.id!r}: disposition {enforce.disposition!r} is invalid"
            )
        if enforce.disposition == "require_approval" and not enforce.require_role:
            raise PolicyValidationError(
                f"rule {rule.id!r}: require_approval needs 'require_role'"
            )


def _self_test() -> None:
    """Validate a good policy and confirm a duplicate id is rejected."""
    from compliance_runtime.policy.models import (
        PolicyEnforcement,
        PolicyRule,
    )

    good = Policy(
        name="p",
        version="1.0.0",
        rules=[
            PolicyRule(
                id="r1",
                priority=10,
                description="d",
                when=[PolicyCondition(field="parameters.amount",
                                      operator="greater_than", value=500)],
                enforce=PolicyEnforcement(
                    disposition="require_approval",
                    reason="r",
                    require_role="compliance_officer",
                ),
            )
        ],
    )
    validate_policy(good)

    bad = good.model_copy(deep=True)
    bad.rules.append(bad.rules[0].model_copy(update={"priority": 20}))
    try:
        validate_policy(bad)
    except PolicyValidationError:
        pass
    else:  # pragma: no cover
        raise AssertionError("duplicate rule id not rejected")

    print("policy.validators self-test: PASS")


if __name__ == "__main__":
    _self_test()
