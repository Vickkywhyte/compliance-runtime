"""Shared pytest fixtures for the test suite."""

from __future__ import annotations

import sqlite3

import pytest

from compliance_runtime.storage.action_records import ActionRecordRepository
from compliance_runtime.storage.evaluations import EvaluationRepository
from compliance_runtime.storage.models import (
    ActionRecord,
    PolicyEvaluation,
    ToolCall,
)
from compliance_runtime.storage.tool_calls import ToolCallRepository
from compliance_runtime.utils.ids import new_ulid, now_utc


@pytest.fixture()
def seed_action_record():
    """Return a factory that seeds one FK-valid action_record and returns its id.

    ``approval_requests.action_id`` references ``action_records``; the approval
    tests reuse a single seeded action record (tool_call -> policy_evaluation
    -> action_record) so foreign keys stay enforced without rebuilding a signed
    hash chain per request.
    """

    def _seed(conn: sqlite3.Connection) -> str:
        call_id, eval_id, action_id = new_ulid(), new_ulid(), new_ulid()
        ToolCallRepository(conn).insert(
            ToolCall(
                call_id=call_id, correlation_id=new_ulid(), agent_id="a",
                session_id="s", action="issue_refund", parameters={"amount": 1},
                received_at=now_utc(),
            )
        )
        EvaluationRepository(conn).insert(
            PolicyEvaluation(
                evaluation_id=eval_id, call_id=call_id, matched_rule_id="r",
                matched_rule_priority=1, policy_version="v",
                disposition="require_approval", reason="r", evidence={},
                evaluated_at=now_utc(), evaluation_duration_ms=1,
            )
        )
        ActionRecordRepository(conn).insert(
            ActionRecord(
                action_id=action_id, call_id=call_id, evaluation_id=eval_id,
                disposition="require_approval", agent_id="a", session_id="s",
                action="issue_refund", parameters_hash="h", timestamp=now_utc(),
                previous_hash="GENESIS", current_hash="0" * 64, signature="x",
                signing_key_id="k", runtime_version="0.1.0",
            )
        )
        return action_id

    return _seed
