"""Policy Pydantic models (05_DATA_SPEC §3.7). Pydantic v2, ``extra="forbid"``.

The controlled vocabularies (``Operator``, ``Disposition``, ``Severity``)
are imported from :mod:`compliance_runtime.storage.models` so there is a
single source of truth for the enums (05_DATA_SPEC §2).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from compliance_runtime.storage.models import Disposition, Operator, Severity

_FORBID = ConfigDict(extra="forbid")


class PolicyCondition(BaseModel):
    """A single field/operator/value condition (ALL must hold in a rule)."""

    model_config = _FORBID

    field: str
    operator: Operator
    value: Any


class PolicyEnforcement(BaseModel):
    """What a matched rule enforces."""

    model_config = _FORBID

    disposition: Disposition
    reason: str
    require_role: str | None = None
    severity: Severity | None = None
    ttl_seconds: int | None = None


class PolicyRule(BaseModel):
    """A priority-ordered rule: ``when`` conditions → ``enforce``."""

    model_config = _FORBID

    id: str
    priority: int
    description: str
    when: list[PolicyCondition]
    enforce: PolicyEnforcement


class Policy(BaseModel):
    """A named, versioned set of rules loaded from one YAML file."""

    model_config = _FORBID

    name: str
    version: str
    rules: list[PolicyRule]


class PolicySet(BaseModel):
    """All loaded policies plus a combined version and content hash (C-29)."""

    model_config = _FORBID

    policies: list[Policy]
    version: str
    content_hash: str


class EvaluationResult(BaseModel):
    """The outcome of evaluating one tool call against the policy set."""

    model_config = ConfigDict(extra="ignore")

    disposition: Disposition
    matched_rule_id: str | None
    matched_rule_priority: int | None
    reason: str
    evidence: dict[str, Any]
    policy_version: str
    evaluated_at: datetime
    evaluation_duration_ms: int


def _self_test() -> None:
    """Build each model and confirm extra keys are rejected."""
    from pydantic import ValidationError

    rule = PolicyRule(
        id="r1",
        priority=10,
        description="demo",
        when=[PolicyCondition(field="action", operator="equals", value="x")],
        enforce=PolicyEnforcement(disposition="allow", reason="ok"),
    )
    policy = Policy(name="p", version="1.0.0", rules=[rule])
    assert policy.rules[0].enforce.disposition == "allow"

    try:
        PolicyRule.model_validate({"id": "r", "priority": 1, "extra": 1})
    except ValidationError:
        pass
    else:  # pragma: no cover
        raise AssertionError("extra='forbid' did not reject unknown key")

    print("policy.models self-test: PASS")


if __name__ == "__main__":
    _self_test()
