"""Approval integrity: single-writer, optimistic lock, concurrency (C-21–C-27).

The concurrency tests use REAL threads against a file-based SQLite DB (each
thread with its own connection), which is the production case. A
``threading.Barrier`` releases all deciders at once so they genuinely race.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from compliance_runtime.approvals.service import ApprovalService
from compliance_runtime.exceptions import (
    ApprovalError,
    ConcurrentModificationError,
    ExpiredApprovalError,
)
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


def _build_service(conn: sqlite3.Connection) -> ApprovalService:
    return ApprovalService(
        ApprovalRequestRepository(conn),
        ApprovalDecisionRepository(conn),
        AuditRepository(conn),
        conn,
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


def _seed_action_record(conn: sqlite3.Connection) -> str:
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


# --- in-memory fixture for single-threaded tests -------------------------


@pytest.fixture()
def mem_ctx(
    seed_action_record: Callable[[sqlite3.Connection], str],
) -> Iterator[tuple[ApprovalService, sqlite3.Connection, str]]:
    conn = get_connection(":memory:")
    apply_migrations(conn)
    action_id = seed_action_record(conn)
    yield _build_service(conn), conn, action_id
    conn.close()


def _request(service: ApprovalService, action_id: str, ttl: int = 900):
    return service.request_approval(
        _call(), _evaluation(), action_id=action_id,
        assignee_role="compliance_officer", severity="high", ttl_seconds=ttl,
    )


# --- concurrency (C-25) --------------------------------------------------


def _run_concurrent(db_path: Path, request_id: str, decisions: list[str]) -> list:
    barrier = threading.Barrier(len(decisions))
    results: list[tuple[str, str]] = []
    lock = threading.Lock()

    def worker(i: int, decision: str) -> None:
        conn = get_connection(str(db_path))
        service = _build_service(conn)
        kwargs = {}
        if decision == "deny":
            kwargs["rationale"] = "no"
        barrier.wait()
        try:
            service.decide(request_id, f"actor_{i}", "compliance_officer",
                           decision, **kwargs)
            outcome = ("ok", decision)
        except ConcurrentModificationError:
            outcome = ("conflict", decision)
        except Exception as exc:  # noqa: BLE001 - record any other outcome
            outcome = ("error", type(exc).__name__)
        finally:
            conn.close()
        with lock:
            results.append(outcome)

    threads = [
        threading.Thread(target=worker, args=(i, d))
        for i, d in enumerate(decisions)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def test_concurrent_approvals_have_single_winner(tmp_path: Path) -> None:
    db = tmp_path / "approvals.db"
    conn = get_connection(str(db))
    apply_migrations(conn)
    action_id = _seed_action_record(conn)
    req = _request(_build_service(conn), action_id)
    conn.close()

    results = _run_concurrent(db, req.request_id, ["approve"] * 5)
    assert sum(1 for r in results if r[0] == "ok") == 1
    assert sum(1 for r in results if r[0] == "conflict") == 4


def test_concurrent_deny_and_approve_have_single_winner(tmp_path: Path) -> None:
    db = tmp_path / "approvals.db"
    conn = get_connection(str(db))
    apply_migrations(conn)
    action_id = _seed_action_record(conn)
    req = _request(_build_service(conn), action_id)
    conn.close()

    results = _run_concurrent(
        db, req.request_id, ["approve", "deny", "approve", "deny", "approve"]
    )
    assert sum(1 for r in results if r[0] == "ok") == 1
    assert sum(1 for r in results if r[0] == "conflict") == 4


# --- terminal-state rejection (C-24) -------------------------------------


def test_approved_cannot_be_approved_again(mem_ctx) -> None:
    service, _, action_id = mem_ctx
    req = _request(service, action_id)
    service.decide(req.request_id, "u", "compliance_officer", "approve")
    with pytest.raises(ApprovalError):
        service.decide(req.request_id, "u", "compliance_officer", "approve")


def test_denied_cannot_be_approved(mem_ctx) -> None:
    service, _, action_id = mem_ctx
    req = _request(service, action_id)
    service.decide(req.request_id, "u", "compliance_officer", "deny", rationale="no")
    with pytest.raises(ApprovalError):
        service.decide(req.request_id, "u", "compliance_officer", "approve")


def test_modified_approved_cannot_be_denied(mem_ctx) -> None:
    service, _, action_id = mem_ctx
    req = _request(service, action_id)
    service.decide(req.request_id, "u", "compliance_officer", "modify_approve",
                   edits={"amount": 1})
    with pytest.raises(ApprovalError):
        service.decide(req.request_id, "u", "compliance_officer", "deny",
                       rationale="no")


def test_expired_cannot_be_approved(mem_ctx) -> None:
    service, _, action_id = mem_ctx
    req = _request(service, action_id, ttl=0)
    with pytest.raises(ExpiredApprovalError):
        service.decide(req.request_id, "u", "compliance_officer", "approve")


# --- optimistic lock (C-22) ----------------------------------------------


def test_optimistic_lock_prevents_stale_write(mem_ctx) -> None:
    service, conn, action_id = mem_ctx
    req = _request(service, action_id)
    repo = ApprovalRequestRepository(conn)
    # Bump the version out from under a would-be writer holding version 1.
    conn.execute(
        "UPDATE approval_requests SET version = 2 WHERE request_id = ?",
        (req.request_id,),
    )
    conn.commit()
    # A write with the now-stale expected_version must not apply.
    assert repo.update_state_with_lock(req.request_id, 1, "approved") is False
    assert repo.get_by_id(req.request_id).state == "pending"


# --- same-transaction audit (C-23) ---------------------------------------


def test_approval_writes_audit_event_in_same_transaction(mem_ctx) -> None:
    service, conn, action_id = mem_ctx
    req = _request(service, action_id)

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated failure after decision insert")

    service._requests.update_state_with_lock = _boom  # type: ignore[assignment]
    with pytest.raises(RuntimeError):
        service.decide(req.request_id, "u", "compliance_officer", "approve")

    # Neither the decision nor a "decided" audit event survived the rollback.
    assert ApprovalDecisionRepository(conn).get_by_request(req.request_id) == []
    chain = service.audit_chain_for_request(req.request_id)
    assert [e.action for e in chain] == ["approval_requested"]


def test_audit_chain_is_complete_for_approved_request(mem_ctx) -> None:
    service, _, action_id = mem_ctx
    req = _request(service, action_id)
    service.decide(req.request_id, "u", "compliance_officer", "approve")
    chain = service.audit_chain_for_request(req.request_id)
    assert [e.action for e in chain] == ["approval_requested", "approval_decided"]


# --- append-only decisions (C-24 / C-10) ---------------------------------


def test_direct_sql_update_of_decisions_rejected(mem_ctx) -> None:
    service, conn, action_id = mem_ctx
    req = _request(service, action_id)
    service.decide(req.request_id, "u", "compliance_officer", "approve")
    with pytest.raises((sqlite3.IntegrityError, sqlite3.OperationalError)):
        conn.execute("UPDATE approval_decisions SET rationale = 'x'")
        conn.commit()
