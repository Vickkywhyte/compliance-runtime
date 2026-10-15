#!/usr/bin/env python
"""Phase 2 migration + round-trip self-test (Lesson 5, C-10).

Applies migrations to a fresh in-memory DB, inserts one of every entity
through its repository, reads each back and asserts equality, then confirms
that UPDATE/DELETE on the append-only tables are rejected. Exits non-zero on
any failure.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from compliance_runtime.storage.action_records import ActionRecordRepository
from compliance_runtime.storage.approvals import (
    ApprovalDecisionRepository,
    ApprovalRequestRepository,
)
from compliance_runtime.storage.audit import AuditRepository
from compliance_runtime.storage.db import get_connection
from compliance_runtime.storage.evaluations import EvaluationRepository
from compliance_runtime.storage.migrate import apply_migrations, migration_status
from compliance_runtime.storage.models import (
    ActionRecord,
    ApprovalDecision,
    ApprovalRequest,
    AuditEvent,
    PolicyEvaluation,
    ToolCall,
)
from compliance_runtime.storage.tool_calls import ToolCallRepository

_FIXTURE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "sample_records.json"


def main() -> int:
    passed = 0
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))

    conn = get_connection(":memory:")
    apply_migrations(conn)

    assert migration_status(conn) == ["001_initial"]
    passed += 1

    # --- insert + read-back round trips (in FK order) --------------------
    call = ToolCall.model_validate(data["tool_call"])
    tc_repo = ToolCallRepository(conn)
    tc_repo.insert(call)
    assert tc_repo.get_by_id(call.call_id) == call
    passed += 1

    evaluation = PolicyEvaluation.model_validate(data["policy_evaluation"])
    ev_repo = EvaluationRepository(conn)
    ev_repo.insert(evaluation)
    assert ev_repo.get_by_id(evaluation.evaluation_id) == evaluation
    passed += 1

    record = ActionRecord.model_validate(data["action_record"])
    ar_repo = ActionRecordRepository(conn)
    ar_repo.insert(record)
    assert ar_repo.get_by_id(record.action_id) == record
    passed += 1

    request = ApprovalRequest.model_validate(data["approval_request"])
    req_repo = ApprovalRequestRepository(conn)
    req_repo.insert(request)
    assert req_repo.get_by_id(request.request_id) == request
    passed += 1

    decision = ApprovalDecision.model_validate(data["approval_decision"])
    dec_repo = ApprovalDecisionRepository(conn)
    dec_repo.insert(decision)
    assert dec_repo.get_by_request(request.request_id) == [decision]
    passed += 1

    event = AuditEvent.model_validate(data["audit_event"])
    audit_repo = AuditRepository(conn)
    audit_repo.append(event)
    assert audit_repo.query({"event_id": event.event_id}) == [event]
    passed += 1

    # --- append-only enforcement (C-10) ----------------------------------
    # Use a column that exists in each table so the trigger (not a
    # "no such column" error) is what rejects the UPDATE.
    update_targets = {
        "action_records": "action",
        "approval_decisions": "rationale",
        "audit_events": "action",
    }
    for table, column in update_targets.items():
        try:
            conn.execute(f"UPDATE {table} SET {column} = 'tampered'")
            conn.commit()
            print(f"FAIL: UPDATE on {table} succeeded")
            return 1
        except (sqlite3.IntegrityError, sqlite3.OperationalError):
            passed += 1
        try:
            conn.execute(f"DELETE FROM {table}")
            conn.commit()
            print(f"FAIL: DELETE on {table} succeeded")
            return 1
        except (sqlite3.IntegrityError, sqlite3.OperationalError):
            passed += 1

    conn.close()
    print(f"PASS: all {passed} assertions passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
