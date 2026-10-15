"""Repository insert + read-back tests (Lesson 5, Lesson 3, C-10).

Every insert is read back and compared field-by-field so serialization
bugs surface immediately.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

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
    ApprovalDecision,
    ApprovalRequest,
    AuditEvent,
    PolicyEvaluation,
    ToolCall,
)
from compliance_runtime.storage.tool_calls import ToolCallRepository

_FIXTURE = Path("tests/fixtures/sample_records.json")
_DATA = json.loads(_FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture()
def conn() -> sqlite3.Connection:
    connection = get_connection(":memory:")
    apply_migrations(connection)
    yield connection
    connection.close()


def _seed_call(conn: sqlite3.Connection) -> ToolCall:
    call = ToolCall.model_validate(_DATA["tool_call"])
    ToolCallRepository(conn).insert(call)
    return call


def _seed_evaluation(conn: sqlite3.Connection) -> PolicyEvaluation:
    evaluation = PolicyEvaluation.model_validate(_DATA["policy_evaluation"])
    EvaluationRepository(conn).insert(evaluation)
    return evaluation


def _seed_action(conn: sqlite3.Connection) -> ActionRecord:
    _seed_call(conn)
    _seed_evaluation(conn)
    record = ActionRecord.model_validate(_DATA["action_record"])
    ActionRecordRepository(conn).insert(record)
    return record


def _seed_request(conn: sqlite3.Connection) -> ApprovalRequest:
    _seed_action(conn)
    request = ApprovalRequest.model_validate(_DATA["approval_request"])
    ApprovalRequestRepository(conn).insert(request)
    return request


# --- ToolCallRepository --------------------------------------------------


def test_tool_call_insert_and_read_back(conn: sqlite3.Connection) -> None:
    call = _seed_call(conn)
    assert ToolCallRepository(conn).get_by_id(call.call_id) == call


def test_tool_call_json_serialization_round_trip(conn: sqlite3.Connection) -> None:
    call = _seed_call(conn)
    got = ToolCallRepository(conn).get_by_id(call.call_id)
    assert got is not None
    assert got.parameters == call.parameters
    assert got.metadata == call.metadata


def test_tool_call_missing_row_returns_none(conn: sqlite3.Connection) -> None:
    assert ToolCallRepository(conn).get_by_id("nope") is None


def test_tool_call_count_increases_after_insert(conn: sqlite3.Connection) -> None:
    repo = ToolCallRepository(conn)
    assert repo.count() == 0
    _seed_call(conn)
    assert repo.count() == 1


def test_tool_call_get_by_correlation(conn: sqlite3.Connection) -> None:
    call = _seed_call(conn)
    got = ToolCallRepository(conn).get_by_correlation(call.correlation_id)
    assert got == [call]


# --- EvaluationRepository ------------------------------------------------


def test_evaluation_insert_and_read_back(conn: sqlite3.Connection) -> None:
    _seed_call(conn)
    evaluation = _seed_evaluation(conn)
    assert EvaluationRepository(conn).get_by_id(evaluation.evaluation_id) == evaluation


def test_evaluation_json_serialization_round_trip(conn: sqlite3.Connection) -> None:
    _seed_call(conn)
    evaluation = _seed_evaluation(conn)
    got = EvaluationRepository(conn).get_by_id(evaluation.evaluation_id)
    assert got is not None and got.evidence == evaluation.evidence


def test_evaluation_missing_row_returns_none(conn: sqlite3.Connection) -> None:
    assert EvaluationRepository(conn).get_by_id("nope") is None


def test_evaluation_count_increases_after_insert(conn: sqlite3.Connection) -> None:
    repo = EvaluationRepository(conn)
    assert repo.count() == 0
    _seed_call(conn)
    _seed_evaluation(conn)
    assert repo.count() == 1


def test_evaluation_get_by_call(conn: sqlite3.Connection) -> None:
    call = _seed_call(conn)
    evaluation = _seed_evaluation(conn)
    assert EvaluationRepository(conn).get_by_call(call.call_id) == [evaluation]


# --- ActionRecordRepository ----------------------------------------------


def test_action_record_insert_and_read_back(conn: sqlite3.Connection) -> None:
    record = _seed_action(conn)
    assert ActionRecordRepository(conn).get_by_id(record.action_id) == record


def test_action_record_missing_row_returns_none(conn: sqlite3.Connection) -> None:
    assert ActionRecordRepository(conn).get_by_id("nope") is None


def test_action_record_count_increases_after_insert(conn: sqlite3.Connection) -> None:
    repo = ActionRecordRepository(conn)
    assert repo.count() == 0
    _seed_action(conn)
    assert repo.count() == 1


def test_action_record_latest_returns_last_inserted(conn: sqlite3.Connection) -> None:
    first = _seed_action(conn)
    repo = ActionRecordRepository(conn)
    # Second record must continue the chain from the first.
    second = first.model_copy(
        update={
            "action_id": "01M4Z7G2C1MV8B9SEKQQRA1ZZZ",
            "previous_hash": first.current_hash,
            "current_hash": "ff" * 32,
        }
    )
    repo.insert(second)
    assert repo.count() == 2
    latest = repo.latest()
    assert latest is not None and latest.action_id == second.action_id


def test_action_record_broken_chain_raises(conn: sqlite3.Connection) -> None:
    from compliance_runtime.exceptions import ChainIntegrityError

    _seed_call(conn)
    _seed_evaluation(conn)
    bad = ActionRecord.model_validate(_DATA["action_record"]).model_copy(
        update={"previous_hash": "not-genesis"}
    )
    with pytest.raises(ChainIntegrityError):
        ActionRecordRepository(conn).insert(bad)


def test_action_record_update_raises(conn: sqlite3.Connection) -> None:
    _seed_action(conn)
    with pytest.raises((sqlite3.IntegrityError, sqlite3.OperationalError)):
        conn.execute("UPDATE action_records SET action = 'x'")
        conn.commit()


def test_action_record_delete_raises(conn: sqlite3.Connection) -> None:
    _seed_action(conn)
    with pytest.raises((sqlite3.IntegrityError, sqlite3.OperationalError)):
        conn.execute("DELETE FROM action_records")
        conn.commit()


# --- ApprovalRequestRepository -------------------------------------------


def test_approval_request_insert_and_read_back(conn: sqlite3.Connection) -> None:
    request = _seed_request(conn)
    assert ApprovalRequestRepository(conn).get_by_id(request.request_id) == request


def test_approval_request_missing_row_returns_none(conn: sqlite3.Connection) -> None:
    assert ApprovalRequestRepository(conn).get_by_id("nope") is None


def test_approval_request_count_increases_after_insert(
    conn: sqlite3.Connection,
) -> None:
    repo = ApprovalRequestRepository(conn)
    assert repo.count_by_state("pending") == 0
    _seed_request(conn)
    assert repo.count_by_state("pending") == 1


def test_list_pending_filters_by_role(conn: sqlite3.Connection) -> None:
    request = _seed_request(conn)
    repo = ApprovalRequestRepository(conn)
    assert repo.list_pending(role=request.assignee_role) == [request]
    assert repo.list_pending(role="someone_else") == []


def test_list_pending_returns_only_pending(conn: sqlite3.Connection) -> None:
    request = _seed_request(conn)
    repo = ApprovalRequestRepository(conn)
    # Insert a second, non-pending request (different action to satisfy FK).
    approved = request.model_copy(
        update={"request_id": "01M4Z7G2C1517Q07VMEDBT3ZZZ", "state": "approved"}
    )
    repo.insert(approved)
    pending = repo.list_pending()
    assert [r.request_id for r in pending] == [request.request_id]


# --- ApprovalDecisionRepository ------------------------------------------


def test_approval_decision_insert_and_read_back(conn: sqlite3.Connection) -> None:
    _seed_request(conn)
    decision = ApprovalDecision.model_validate(_DATA["approval_decision"])
    repo = ApprovalDecisionRepository(conn)
    repo.insert(decision)
    assert repo.get_by_request(decision.request_id) == [decision]


def test_approval_decision_json_round_trip_with_edits(
    conn: sqlite3.Connection,
) -> None:
    _seed_request(conn)
    decision = ApprovalDecision.model_validate(_DATA["approval_decision"]).model_copy(
        update={
            "decision_id": "01M4Z7G2C14ADJ239FX3YHBZZZ",
            "decision": "modify_approve",
            "edits": {"amount": 500},
        }
    )
    repo = ApprovalDecisionRepository(conn)
    repo.insert(decision)
    got = repo.get_by_request(decision.request_id)
    assert got[-1].edits == {"amount": 500}


def test_approval_decision_count_increases_after_insert(
    conn: sqlite3.Connection,
) -> None:
    _seed_request(conn)
    repo = ApprovalDecisionRepository(conn)
    assert repo.count() == 0
    repo.insert(ApprovalDecision.model_validate(_DATA["approval_decision"]))
    assert repo.count() == 1


def test_approval_decision_update_raises(conn: sqlite3.Connection) -> None:
    _seed_request(conn)
    ApprovalDecisionRepository(conn).insert(
        ApprovalDecision.model_validate(_DATA["approval_decision"])
    )
    with pytest.raises((sqlite3.IntegrityError, sqlite3.OperationalError)):
        conn.execute("UPDATE approval_decisions SET rationale = 'x'")
        conn.commit()


# --- AuditRepository (append-only) ---------------------------------------


def test_audit_insert_and_read_back(conn: sqlite3.Connection) -> None:
    event = AuditEvent.model_validate(_DATA["audit_event"])
    repo = AuditRepository(conn)
    repo.append(event)
    assert repo.query({"event_id": event.event_id}) == [event]


def test_audit_json_round_trip(conn: sqlite3.Connection) -> None:
    event = AuditEvent.model_validate(_DATA["audit_event"])
    repo = AuditRepository(conn)
    repo.append(event)
    got = repo.query({"event_id": event.event_id})[0]
    assert got.payload == event.payload


def test_audit_update_raises(conn: sqlite3.Connection) -> None:
    AuditRepository(conn).append(AuditEvent.model_validate(_DATA["audit_event"]))
    with pytest.raises((sqlite3.IntegrityError, sqlite3.OperationalError)):
        conn.execute("UPDATE audit_events SET action = 'x'")
        conn.commit()


def test_audit_delete_raises(conn: sqlite3.Connection) -> None:
    AuditRepository(conn).append(AuditEvent.model_validate(_DATA["audit_event"]))
    with pytest.raises((sqlite3.IntegrityError, sqlite3.OperationalError)):
        conn.execute("DELETE FROM audit_events")
        conn.commit()


# --- Raw-connection regression (repos must not depend on row_factory) ----


def test_repositories_work_with_raw_connection() -> None:
    # A plain connection with the default tuple row factory must behave
    # the same as one from get_connection(): repos set row_factory=Row.
    raw = sqlite3.connect(":memory:")
    try:
        apply_migrations(raw)
        call = ToolCall.model_validate(_DATA["tool_call"])
        tc_repo = ToolCallRepository(raw)
        tc_repo.insert(call)
        assert tc_repo.get_by_id(call.call_id) == call
    finally:
        raw.close()


def test_chain_guard_raises_typed_error_on_raw_connection() -> None:
    from compliance_runtime.exceptions import ChainIntegrityError

    raw = sqlite3.connect(":memory:")
    try:
        apply_migrations(raw)
        ToolCallRepository(raw).insert(ToolCall.model_validate(_DATA["tool_call"]))
        EvaluationRepository(raw).insert(
            PolicyEvaluation.model_validate(_DATA["policy_evaluation"])
        )
        repo = ActionRecordRepository(raw)
        repo.insert(ActionRecord.model_validate(_DATA["action_record"]))
        # Second record with a previous_hash that does not continue the chain
        # must raise ChainIntegrityError (not a ValueError from dict(tuple)).
        bad = ActionRecord.model_validate(_DATA["action_record"]).model_copy(
            update={
                "action_id": "01M4Z7G2C1MV8B9SEKQQRA1RAW",
                "previous_hash": "WRONG",
                "current_hash": "ab" * 32,
            }
        )
        with pytest.raises(ChainIntegrityError):
            repo.insert(bad)
    finally:
        raw.close()
