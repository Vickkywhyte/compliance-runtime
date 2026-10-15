"""Tests for the approval service (C-21, C-23)."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator

import pytest

from compliance_runtime.approvals.service import ApprovalService
from compliance_runtime.exceptions import ApprovalError
from compliance_runtime.policy.models import EvaluationResult
from compliance_runtime.storage.approvals import (
    ApprovalDecisionRepository,
    ApprovalRequestRepository,
)
from compliance_runtime.storage.audit import AuditRepository
from compliance_runtime.storage.db import get_connection
from compliance_runtime.storage.migrate import apply_migrations
from compliance_runtime.storage.models import ApprovalRequest, ToolCall
from compliance_runtime.utils.ids import new_ulid, now_utc


@pytest.fixture()
def service_ctx(
    seed_action_record: Callable[[sqlite3.Connection], str],
) -> Iterator[tuple[ApprovalService, sqlite3.Connection, str]]:
    conn = get_connection(":memory:")
    apply_migrations(conn)
    action_id = seed_action_record(conn)
    service = ApprovalService(
        ApprovalRequestRepository(conn),
        ApprovalDecisionRepository(conn),
        AuditRepository(conn),
        conn,
    )
    yield service, conn, action_id
    conn.close()


def _call() -> ToolCall:
    return ToolCall(
        call_id=new_ulid(), correlation_id=new_ulid(), agent_id="a",
        session_id="s", action="issue_refund", parameters={"amount": 850},
        received_at=now_utc(),
    )


def _evaluation() -> EvaluationResult:
    return EvaluationResult(
        disposition="require_approval", matched_rule_id="refund_limit",
        matched_rule_priority=10, reason="over limit", evidence={},
        policy_version="p@1.0.0", evaluated_at=now_utc(),
        evaluation_duration_ms=1,
    )


def _request(service: ApprovalService, action_id: str) -> ApprovalRequest:
    return service.request_approval(
        _call(), _evaluation(), action_id=action_id,
        assignee_role="compliance_officer", severity="high", ttl_seconds=900,
    )


def test_request_approval_creates_pending_request(service_ctx) -> None:
    service, conn, action_id = service_ctx
    req = _request(service, action_id)
    assert req.state == "pending"
    assert req.version == 1
    assert ApprovalRequestRepository(conn).get_by_id(req.request_id) is not None


def test_request_approval_writes_audit_event(service_ctx) -> None:
    service, _, action_id = service_ctx
    req = _request(service, action_id)
    chain = service.audit_chain_for_request(req.request_id)
    assert [e.action for e in chain] == ["approval_requested"]


def test_decision_approve_transitions_state(service_ctx) -> None:
    service, conn, action_id = service_ctx
    req = _request(service, action_id)
    service.decide(req.request_id, "u", "compliance_officer", "approve")
    assert ApprovalRequestRepository(conn).get_by_id(req.request_id).state == "approved"


def test_decision_deny_transitions_state(service_ctx) -> None:
    service, conn, action_id = service_ctx
    req = _request(service, action_id)
    service.decide(req.request_id, "u", "compliance_officer", "deny",
                   rationale="not allowed")
    assert ApprovalRequestRepository(conn).get_by_id(req.request_id).state == "denied"


def test_decision_modify_approve_transitions_state(service_ctx) -> None:
    service, conn, action_id = service_ctx
    req = _request(service, action_id)
    service.decide(req.request_id, "u", "compliance_officer", "modify_approve",
                   edits={"amount": 500})
    assert (
        ApprovalRequestRepository(conn).get_by_id(req.request_id).state
        == "modified_approved"
    )


def test_decision_records_actor(service_ctx) -> None:
    service, conn, action_id = service_ctx
    req = _request(service, action_id)
    decision = service.decide(req.request_id, "officer_7", "compliance_officer",
                              "approve")
    stored = ApprovalDecisionRepository(conn).get_by_request(req.request_id)
    assert stored[0].actor_id == "officer_7"
    assert decision.actor_id == "officer_7"


def test_decision_records_timestamp(service_ctx) -> None:
    service, _, action_id = service_ctx
    req = _request(service, action_id)
    decision = service.decide(req.request_id, "u", "compliance_officer", "approve")
    assert decision.decided_at is not None


def test_decision_deny_requires_rationale(service_ctx) -> None:
    service, _, action_id = service_ctx
    req = _request(service, action_id)
    with pytest.raises(ApprovalError):
        service.decide(req.request_id, "u", "compliance_officer", "deny")


def test_decision_modify_requires_edits(service_ctx) -> None:
    service, _, action_id = service_ctx
    req = _request(service, action_id)
    with pytest.raises(ApprovalError):
        service.decide(req.request_id, "u", "compliance_officer", "modify_approve")


def test_decide_on_nonexistent_request_raises(service_ctx) -> None:
    service, _, _ = service_ctx
    with pytest.raises(ApprovalError):
        service.decide("no_such_id", "u", "compliance_officer", "approve")


def test_decide_on_terminal_state_raises(service_ctx) -> None:
    service, _, action_id = service_ctx
    req = _request(service, action_id)
    service.decide(req.request_id, "u", "compliance_officer", "approve")
    with pytest.raises(ApprovalError):
        service.decide(req.request_id, "u", "compliance_officer", "deny",
                       rationale="too late")


def test_audit_chain_for_request_returns_events_in_order(service_ctx) -> None:
    service, _, action_id = service_ctx
    req = _request(service, action_id)
    service.decide(req.request_id, "u", "compliance_officer", "approve")
    chain = service.audit_chain_for_request(req.request_id)
    assert [e.action for e in chain] == ["approval_requested", "approval_decided"]


def test_list_pending_filters_by_role(service_ctx) -> None:
    service, _, action_id = service_ctx
    req = _request(service, action_id)
    assert [r.request_id for r in service.list_pending("compliance_officer")] == [
        req.request_id
    ]
    assert service.list_pending("some_other_role") == []


def test_list_pending_excludes_expired(service_ctx) -> None:
    service, conn, action_id = service_ctx
    # A request with ttl_seconds=0 is already expired at creation.
    expired = service.request_approval(
        _call(), _evaluation(), action_id=action_id,
        assignee_role="compliance_officer", severity="high", ttl_seconds=0,
    )
    pending = service.list_pending("compliance_officer")
    assert expired.request_id not in [r.request_id for r in pending]
