"""Tests for the four disposition handlers (ADR-006)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from compliance_runtime.dispositions import (
    dispatch_disposition,
    handle_allow,
    handle_approval,
    handle_deny,
    handle_flagged,
)
from compliance_runtime.policy.models import EvaluationResult
from compliance_runtime.storage.models import ActionRecord, ApprovalRequest, ToolCall
from compliance_runtime.utils.ids import new_ulid, now_utc

_POLICY_VERSION = "demo_policy@1.0.0+abc"


def _call() -> ToolCall:
    return ToolCall(
        call_id=new_ulid(), correlation_id=new_ulid(), agent_id="a",
        session_id="s", action="issue_refund", parameters={"amount": 1},
        received_at=now_utc(),
    )


def _evaluation(disposition: str, rule_id: str | None) -> EvaluationResult:
    return EvaluationResult(
        disposition=disposition, matched_rule_id=rule_id,
        matched_rule_priority=10, reason=f"{disposition} reason",
        evidence={"parameters.amount": 1}, policy_version=_POLICY_VERSION,
        evaluated_at=now_utc(), evaluation_duration_ms=1,
    )


def _action_record() -> ActionRecord:
    return ActionRecord(
        action_id=new_ulid(), call_id=new_ulid(), evaluation_id=new_ulid(),
        disposition="allow", agent_id="a", session_id="s", action="issue_refund",
        parameters_hash="h", timestamp=now_utc(), previous_hash="GENESIS",
        current_hash="0" * 64, signature="x", signing_key_id="k",
        runtime_version="0.1.0",
    )


def _approval_request() -> ApprovalRequest:
    created = now_utc()
    return ApprovalRequest(
        request_id=new_ulid(), action_id=new_ulid(), call_id=new_ulid(),
        reason="over limit", matched_rule_id="refund_limit", severity="high",
        assignee_role="compliance_officer", ttl_seconds=900, created_at=created,
        expires_at=created + timedelta(seconds=900), state="pending", version=1,
    )


def test_allow_response_shape() -> None:
    resp = handle_allow(_call(), _evaluation("allow", "r"), _action_record(),
                        _POLICY_VERSION)
    assert resp.disposition == "allow"
    assert resp.success is True
    assert resp.result == {"status": "allowed"}
    assert resp.error is None


def test_deny_response_shape() -> None:
    resp = handle_deny(_call(), _evaluation("deny", "fraud_flagged_account"),
                       _action_record(), _POLICY_VERSION)
    assert resp.success is False
    assert resp.error["code"] == "POLICY_DENIED"
    assert resp.error["rule_id"] == "fraud_flagged_account"
    assert resp.error["evidence"] == {"parameters.amount": 1}


def test_approval_response_shape() -> None:
    request = _approval_request()
    resp = handle_approval(_call(), _evaluation("require_approval", "refund_limit"),
                           _action_record(), request, _POLICY_VERSION)
    assert resp.success is None
    assert resp.status == "pending"
    assert resp.request_id == request.request_id
    assert resp.expires_at == request.expires_at


def test_flagged_response_shape() -> None:
    resp = handle_flagged(_call(), _evaluation("allow_with_flag", None),
                          _action_record(), _POLICY_VERSION)
    assert resp.success is True
    assert resp.result == {"status": "allowed"}
    assert "allowed_with_flag" in resp.warnings


def test_dispatch_unknown_disposition_raises() -> None:
    with pytest.raises(ValueError):
        dispatch_disposition("teleport", _call(), _evaluation("allow", "r"),
                             _action_record(), _POLICY_VERSION)


def test_dispatch_approval_without_request_raises() -> None:
    with pytest.raises(ValueError):
        dispatch_disposition("require_approval", _call(),
                             _evaluation("require_approval", "r"),
                             _action_record(), _POLICY_VERSION,
                             approval_request=None)


def test_all_handlers_pure() -> None:
    # Pure: identical inputs → identical output, no I/O, repeatable.
    call = _call()
    evaluation = _evaluation("allow", "r")
    record = _action_record()
    first = handle_allow(call, evaluation, record, _POLICY_VERSION)
    second = handle_allow(call, evaluation, record, _POLICY_VERSION)
    assert first.model_dump() == second.model_dump()
