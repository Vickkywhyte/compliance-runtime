"""TTL expiry for approval requests (ADR-007, C-26).

Expired requests are treated as denials: a pending request past its
``expires_at`` transitions to ``expired`` and cannot be resurrected. Expiry
writes an audit event in the same transaction as the state change (C-23).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from compliance_runtime.storage.approvals import ApprovalRequestRepository
from compliance_runtime.storage.audit import AuditRepository
from compliance_runtime.storage.models import ApprovalRequest, AuditEvent
from compliance_runtime.utils.ids import new_ulid, now_utc

_BUSY_TIMEOUT_MS = 5000


@contextmanager
def immediate_transaction(conn: sqlite3.Connection) -> Iterator[None]:
    """Run a block inside a single ``BEGIN IMMEDIATE`` transaction.

    Sets autocommit control to manual so the explicit transaction is the only
    one in play, and a busy timeout so concurrent writers queue rather than
    fail. Commits on success, rolls back and re-raises on any exception.
    """
    conn.isolation_level = None
    conn.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def is_expired(request: ApprovalRequest) -> bool:
    """Return True if the request's TTL has elapsed."""
    return request.expires_at <= now_utc()


def expire_if_needed(
    request: ApprovalRequest,
    repo: ApprovalRequestRepository,
    audit_repo: AuditRepository,
) -> bool:
    """Expire a pending, past-TTL request atomically. Return True if applied."""
    if request.state != "pending" or not is_expired(request):
        return False

    conn = repo._conn  # same connection backs repo + audit_repo
    try:
        with immediate_transaction(conn):
            updated = repo.update_state_with_lock(
                request.request_id, request.version, "expired", commit=False
            )
            if not updated:
                # Lost a race (already decided/expired); nothing to do.
                raise _NoChange()
            audit_repo.append(
                AuditEvent(
                    event_id=new_ulid(),
                    occurred_at=now_utc(),
                    actor_type="system",
                    actor_id="system",
                    action="approval_expired",
                    entity_type="approval_request",
                    entity_id=request.request_id,
                    correlation_id=request.call_id,
                    payload={"reason": "ttl_elapsed"},
                ),
                commit=False,
            )
    except _NoChange:
        return False
    return True


class _NoChange(Exception):
    """Internal: a concurrent writer already moved the request."""


def _self_test() -> None:
    """Expire a past-TTL request and confirm the state + audit event."""
    from datetime import timedelta

    from compliance_runtime.storage.action_records import ActionRecordRepository
    from compliance_runtime.storage.db import get_connection
    from compliance_runtime.storage.evaluations import EvaluationRepository
    from compliance_runtime.storage.migrate import apply_migrations
    from compliance_runtime.storage.models import (
        ActionRecord,
        PolicyEvaluation,
        ToolCall,
    )
    from compliance_runtime.storage.tool_calls import ToolCallRepository

    conn = get_connection(":memory:")
    apply_migrations(conn)
    repo = ApprovalRequestRepository(conn)
    audit = AuditRepository(conn)

    # Seed one FK parent (tool_call -> evaluation -> action_record).
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

    past = now_utc() - timedelta(seconds=10)
    request = ApprovalRequest(
        request_id=new_ulid(), action_id=action_id, call_id=call_id,
        reason="r", matched_rule_id="rule", severity="high",
        assignee_role="compliance_officer", ttl_seconds=5,
        created_at=past - timedelta(seconds=5), expires_at=past,
        state="pending", version=1,
    )
    repo.insert(request)
    assert is_expired(request)
    assert expire_if_needed(request, repo, audit) is True
    assert repo.get_by_id(request.request_id).state == "expired"
    assert expire_if_needed(repo.get_by_id(request.request_id), repo, audit) is False
    print("approvals.ttl self-test: PASS")


if __name__ == "__main__":
    _self_test()
