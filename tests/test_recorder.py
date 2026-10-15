"""Tests for the evidence recorder (ADR-004, C-37, Lesson 5)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from compliance_runtime.config.keys import get_or_create_signing_key, set_keys_dir
from compliance_runtime.evidence.hashing import GENESIS_HASH, canonicalize, sha256_hex
from compliance_runtime.evidence.recorder import EvidenceRecorder
from compliance_runtime.evidence.signing import get_key_id
from compliance_runtime.policy.models import EvaluationResult
from compliance_runtime.storage.action_records import ActionRecordRepository
from compliance_runtime.storage.db import get_connection
from compliance_runtime.storage.evaluations import EvaluationRepository
from compliance_runtime.storage.migrate import apply_migrations
from compliance_runtime.storage.models import PolicyEvaluation, ToolCall
from compliance_runtime.storage.tool_calls import ToolCallRepository
from compliance_runtime.utils.ids import new_ulid, now_utc


@pytest.fixture(autouse=True)
def _temp_keys(tmp_path: Path) -> Iterator[None]:
    set_keys_dir(tmp_path)
    get_or_create_signing_key()
    try:
        yield
    finally:
        set_keys_dir(None)


@pytest.fixture()
def conn() -> Iterator[sqlite3.Connection]:
    connection = get_connection(":memory:")
    apply_migrations(connection)
    yield connection
    connection.close()


def _evaluation() -> EvaluationResult:
    return EvaluationResult(
        disposition="allow",
        matched_rule_id="default_allow_refunds",
        matched_rule_priority=100,
        reason="ok",
        evidence={},
        policy_version="demo@1.0.0+abc",
        evaluated_at=now_utc(),
        evaluation_duration_ms=1,
    )


def _record(
    conn: sqlite3.Connection,
    recorder: EvidenceRecorder,
    parameters: dict | None = None,
):
    """Seed the FK parents and record one action; return the ActionRecord."""
    call = ToolCall(
        call_id=new_ulid(),
        correlation_id=new_ulid(),
        agent_id="agent-1",
        session_id="sess-1",
        action="issue_refund",
        parameters=parameters if parameters is not None else {"amount": 100},
        received_at=now_utc(),
    )
    ToolCallRepository(conn).insert(call)
    eid = new_ulid()
    EvaluationRepository(conn).insert(
        PolicyEvaluation(
            evaluation_id=eid,
            call_id=call.call_id,
            matched_rule_id="default_allow_refunds",
            matched_rule_priority=100,
            policy_version="demo@1.0.0+abc",
            disposition="allow",
            reason="ok",
            evidence={},
            evaluated_at=now_utc(),
            evaluation_duration_ms=1,
        )
    )
    return call, recorder.record(call, _evaluation(), evaluation_id=eid)


def test_record_creates_action_record(conn: sqlite3.Connection) -> None:
    recorder = EvidenceRecorder(ActionRecordRepository(conn))
    call, record = _record(conn, recorder)
    assert record.call_id == call.call_id
    assert record.disposition == "allow"
    assert len(record.current_hash) == 64
    assert record.signature


def test_first_record_has_genesis_previous_hash(conn: sqlite3.Connection) -> None:
    recorder = EvidenceRecorder(ActionRecordRepository(conn))
    _, record = _record(conn, recorder)
    assert record.previous_hash == GENESIS_HASH


def test_second_record_links_to_first(conn: sqlite3.Connection) -> None:
    recorder = EvidenceRecorder(ActionRecordRepository(conn))
    _, first = _record(conn, recorder)
    _, second = _record(conn, recorder)
    assert second.previous_hash == first.current_hash


def test_parameters_hash_is_sha256_of_canonical_json(conn: sqlite3.Connection) -> None:
    recorder = EvidenceRecorder(ActionRecordRepository(conn))
    params = {"amount": 250, "currency": "EUR"}
    _, record = _record(conn, recorder, parameters=params)
    assert record.parameters_hash == sha256_hex(canonicalize(params))


def test_parameters_hash_differs_for_different_parameters(
    conn: sqlite3.Connection,
) -> None:
    recorder = EvidenceRecorder(ActionRecordRepository(conn))
    _, a = _record(conn, recorder, parameters={"amount": 100})
    _, b = _record(conn, recorder, parameters={"amount": 200})
    assert a.parameters_hash != b.parameters_hash


def test_record_stores_key_id(conn: sqlite3.Connection) -> None:
    recorder = EvidenceRecorder(ActionRecordRepository(conn))
    _, record = _record(conn, recorder)
    assert record.signing_key_id == get_key_id()


def test_record_stores_runtime_version(conn: sqlite3.Connection) -> None:
    from compliance_runtime import __version__

    recorder = EvidenceRecorder(ActionRecordRepository(conn))
    _, record = _record(conn, recorder)
    assert record.runtime_version == __version__


def test_recorder_read_back(conn: sqlite3.Connection) -> None:
    repo = ActionRecordRepository(conn)
    recorder = EvidenceRecorder(repo)
    _, record = _record(conn, recorder)
    stored = repo.get_by_id(record.action_id)
    assert stored == record  # field-by-field equality (Lesson 5)
