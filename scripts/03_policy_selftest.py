#!/usr/bin/env python
"""Phase 3 policy self-test (Lesson 2, Lesson 3).

Loads the demo policy, confirms three rules, and evaluates the three
canonical dispositions (allow, deny, require_approval), asserting both the
disposition and the matched rule id. Exits non-zero on any failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

from compliance_runtime.policy.engine import PolicyEngine
from compliance_runtime.policy.loader import load_policy_set
from compliance_runtime.storage.models import ToolCall
from compliance_runtime.utils.ids import new_ulid, now_utc


def _call(amount: object) -> ToolCall:
    return ToolCall(
        call_id=new_ulid(),
        correlation_id=new_ulid(),
        agent_id="support_agent_v3",
        session_id="sess_abc",
        action="issue_refund",
        parameters={"amount": amount},
        received_at=now_utc(),
    )


def main() -> int:
    passed = 0
    ps = load_policy_set(Path("configs/policies"))

    rules = [r for p in ps.policies for r in p.rules]
    assert len(rules) == 3, f"expected 3 rules, got {len(rules)}"
    passed += 1

    engine = PolicyEngine(ps)

    allow = engine.evaluate(_call(100))
    assert allow.disposition == "allow", allow.disposition
    assert allow.matched_rule_id == "default_allow_refunds", allow.matched_rule_id
    passed += 1

    approval = engine.evaluate(_call(750))
    assert approval.disposition == "require_approval", approval.disposition
    assert approval.matched_rule_id == "refund_limit", approval.matched_rule_id
    passed += 1

    deny = engine.evaluate(
        _call(100), entity_context={"fraud_flags": ["chargeback_risk"]}
    )
    assert deny.disposition == "deny", deny.disposition
    assert deny.matched_rule_id == "fraud_flagged_account", deny.matched_rule_id
    passed += 1

    print(f"PASS: all {passed} assertions passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
