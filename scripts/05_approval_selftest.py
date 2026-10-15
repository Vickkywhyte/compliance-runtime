#!/usr/bin/env python
"""Phase 5 approval workflow self-test (Lesson 2, Lesson 5, ADR-007).

Exercises the human-in-the-loop flow end to end on an in-memory DB:
request -> approve, audit chain, terminal rejection, and a separate
request -> deny with a post-deny approval attempt. Exits non-zero on
failure.
"""

from __future__ import annotations

import sys

from compliance_runtime.approvals.service import ApprovalService
from compliance_runtime.exceptions import ApprovalError
from compliance_runtime.policy.models import EvaluationResult
from compliance_runtime.storage.action_records import ActionRecordRepository
from compliance_runtime.storage.approvals import (
    ApprovalDecisionRepository,
    ApprovalRequestRepository,
)
from compliance_runtime.storage.audit import AuditRepository
from compliance_runtime.storage.db import get_connection
from compliance_runtime.storage.evaluations import EvaluationRepository
from compliance_runtime.storage.migrate import apply_migrations
from compliance_runtime.storage.models import (
    ActionRecord,
    PolicyEvaluation,
    ToolCall,
)
from compliance_runtime.storage.tool_calls import ToolCallRepository
from compliance_runtime.utils.ids import new_ulid, now_utc


def _seed_action_record(conn) -> str:
    call_id, eval_id, action_id = new_ulid(), new_ulid(), new_ulid()
    ToolCallRepository(conn).insert(
        ToolCall(call_id=call_id, correlation_id=new_ulid(), agent_id="a",
                 session_id="s", action="issue_refund", parameters={"amount": 1},
                 received_at=now_utc())
    )
    EvaluationRepository(conn).insert(
        PolicyEvaluation(evaluation_id=eval_id, call_id=call_id, matched_rule_id="r",
                         matched_rule_priority=1, policy_version="v",
                         disposition="require_approval", reason="r", evidence={},
                         evaluated_at=now_utc(), evaluation_duration_ms=1)
    )
    ActionRecordRepository(conn).insert(
        ActionRecord(action_id=action_id, call_id=call_id, evaluation_id=eval_id,
                     disposition="require_approval", agent_id="a", session_id="s",
                     action="issue_refund", parameters_hash="h", timestamp=now_utc(),
                     previous_hash="GENESIS", current_hash="0" * 64, signature="x",
                     signing_key_id="k", runtime_version="0.1.0")
    )
    return action_id


def _evaluation() -> EvaluationResult:
    return EvaluationResult(
        disposition="require_approval", matched_rule_id="refund_limit",
        matched_rule_priority=10, reason="over limit", evidence={},
        policy_version="p@1.0.0", evaluated_at=now_utc(), evaluation_duration_ms=1,
    )


def _call() -> ToolCall:
    return ToolCall(
        call_id=new_ulid(), correlation_id=new_ulid(), agent_id="a",
        session_id="s", action="issue_refund", parameters={"amount": 850},
        received_at=now_utc(),
    )


def main() -> int:
    passed = 0
    conn = get_connection(":memory:")
    apply_migrations(conn)
    req_repo = ApprovalRequestRepository(conn)
    service = ApprovalService(
        req_repo, ApprovalDecisionRepository(conn), AuditRepository(conn), conn
    )
    action_id = _seed_action_record(conn)

    req = service.request_approval(
        _call(), _evaluation(), action_id=action_id,
        assignee_role="compliance_officer", severity="high", ttl_seconds=900,
    )
    assert req.state == "pending", req.state
    passed += 1

    service.decide(req.request_id, "officer_1", "compliance_officer", "approve")
    updated = req_repo.get_by_id(req.request_id)
    assert updated.state == "approved", updated.state
    passed += 1
    assert updated.version == 2, updated.version
    passed += 1

    chain = service.audit_chain_for_request(req.request_id)
    assert [e.action for e in chain] == ["approval_requested", "approval_decided"]
    passed += 1

    try:
        service.decide(req.request_id, "officer_1", "compliance_officer", "deny",
                       rationale="too late")
        print("FAIL: second decide on approved request succeeded")
        return 1
    except ApprovalError:
        passed += 1

    req2 = service.request_approval(
        _call(), _evaluation(), action_id=action_id,
        assignee_role="compliance_officer", severity="high", ttl_seconds=900,
    )
    service.decide(req2.request_id, "officer_2", "compliance_officer", "deny",
                   rationale="not permitted")
    assert req_repo.get_by_id(req2.request_id).state == "denied"
    passed += 1

    try:
        service.decide(req2.request_id, "officer_2", "compliance_officer", "approve")
        print("FAIL: approving a denied request succeeded")
        return 1
    except ApprovalError:
        passed += 1

    conn.close()
    print(f"PASS: all {passed} assertions passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
