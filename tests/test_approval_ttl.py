"""Tests for approval TTL expiry (C-26)."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from datetime import timedelta

import pytest

from compliance_runtime.approvals.service import ApprovalService
from compliance_runtime.approvals.ttl import expire_if_needed, is_expired
from compliance_runtime.exceptions import ExpiredApprovalError
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
def ctx(
    seed_action_record: Callable[[sqlite3.Connection], str],
) -> Iterator[tuple[ApprovalService, ApprovalRequestRepository, AuditRepository, str]]:
    conn = get_connection(":memory:")
    apply_migrations(conn)
    action_id = seed_action_record(conn)
    req_repo = ApprovalRequestRepository(conn)
    audit = AuditRepository(conn)
    service = ApprovalService(
        req_repo, ApprovalDecisionRepository(conn), audit, conn
    )
    yield service, req_repo, audit, action_id
    conn.close()


def _make_request(action_id: str, ttl_seconds: int) -> ApprovalRequest:
    created = now_utc()
    return ApprovalRequest(
        request_id=new_ulid(), action_id=action_id, call_id=new_ulid(),
        reason="r", matched_rule_id="rule", severity="high",
        assignee_role="compliance_officer", ttl_seconds=ttl_seconds,
        created_at=created,
        expires_at=created + timedelta(seconds=ttl_seconds),
        state="pending", version=1,
    )


def _evaluation() -> EvaluationResult:
    return EvaluationResult(
        disposition="require_approval", matched_rule_id="refund_limit",
        matched_rule_priority=10, reason="over", evidence={},
        policy_version="p@1.0.0", evaluated_at=now_utc(),
        evaluation_duration_ms=1,
    )


def _call() -> ToolCall:
    return ToolCall(
        call_id=new_ulid(), correlation_id=new_ulid(), agent_id="a",
        session_id="s", action="issue_refund", parameters={"amount": 850},
        received_at=now_utc(),
    )


def test_is_expired_returns_false_for_future_ttl(ctx) -> None:
    _, _, _, action_id = ctx
    assert is_expired(_make_request(action_id, 900)) is False


def test_is_expired_returns_true_for_past_ttl(ctx) -> None:
    _, _, _, action_id = ctx
    assert is_expired(_make_request(action_id, -10)) is True


def test_expire_if_needed_marks_expired(ctx) -> None:
    _, req_repo, audit, action_id = ctx
    req = _make_request(action_id, -10)
    req_repo.insert(req)
    assert expire_if_needed(req, req_repo, audit) is True
    assert req_repo.get_by_id(req.request_id).state == "expired"


def test_expire_if_needed_writes_audit_event(ctx) -> None:
    service, req_repo, audit, action_id = ctx
    req = _make_request(action_id, -10)
    req_repo.insert(req)
    expire_if_needed(req, req_repo, audit)
    chain = service.audit_chain_for_request(req.request_id)
    assert [e.action for e in chain] == ["approval_expired"]


def test_expire_stale_requests_sweeps_multiple(ctx) -> None:
    service, req_repo, _, action_id = ctx
    for _ in range(3):
        req_repo.insert(_make_request(action_id, -10))
    assert service.expire_stale_requests() == 3


def test_expire_stale_requests_is_idempotent(ctx) -> None:
    service, req_repo, _, action_id = ctx
    req_repo.insert(_make_request(action_id, -10))
    assert service.expire_stale_requests() == 1
    assert service.expire_stale_requests() == 0


def test_expired_request_cannot_be_approved(ctx) -> None:
    service, _, _, action_id = ctx
    # ttl_seconds=0 → expired immediately.
    req = service.request_approval(
        _call(), _evaluation(), action_id=action_id,
        assignee_role="compliance_officer", severity="high", ttl_seconds=0,
    )
    with pytest.raises(ExpiredApprovalError):
        service.decide(req.request_id, "u", "compliance_officer", "approve")
