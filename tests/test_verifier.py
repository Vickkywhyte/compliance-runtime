"""Tests for the offline evidence verifier (ADR-004, 09_RUNTIME_DESIGN §7.4)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from compliance_runtime.config.keys import get_or_create_signing_key, set_keys_dir
from compliance_runtime.evidence.recorder import EvidenceRecorder
from compliance_runtime.evidence.signing import sign_hash
from compliance_runtime.evidence.verifier import EvidenceVerifier
from compliance_runtime.policy.models import EvaluationResult
from compliance_runtime.storage.action_records import ActionRecordRepository
from compliance_runtime.storage.db import get_connection
from compliance_runtime.storage.evaluations import EvaluationRepository
from compliance_runtime.storage.migrate import apply_migrations
from compliance_runtime.storage.models import ActionRecord, PolicyEvaluation, ToolCall
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


def _record_n(conn: sqlite3.Connection, n: int) -> list[ActionRecord]:
    recorder = EvidenceRecorder(ActionRecordRepository(conn))
    records: list[ActionRecord] = []
    for _ in range(n):
        call = ToolCall(
            call_id=new_ulid(), correlation_id=new_ulid(), agent_id="a",
            session_id="s", action="issue_refund", parameters={"amount": 100},
            received_at=now_utc(),
        )
        ToolCallRepository(conn).insert(call)
        eid = new_ulid()
        EvaluationRepository(conn).insert(
            PolicyEvaluation(
                evaluation_id=eid, call_id=call.call_id, matched_rule_id="r",
                matched_rule_priority=1, policy_version="v", disposition="allow",
                reason="ok", evidence={}, evaluated_at=now_utc(),
                evaluation_duration_ms=1,
            )
        )
        records.append(
            recorder.record(
                call,
                EvaluationResult(
                    disposition="allow", matched_rule_id="r",
                    matched_rule_priority=1, reason="ok", evidence={},
                    policy_version="v", evaluated_at=now_utc(),
                    evaluation_duration_ms=1,
                ),
                evaluation_id=eid,
            )
        )
    return records


def test_verify_empty_chain(conn: sqlite3.Connection) -> None:
    report = EvidenceVerifier(ActionRecordRepository(conn)).verify_all()
    assert report.chain_integrity is True
    assert report.n_records == 0


def test_verify_single_record(conn: sqlite3.Connection) -> None:
    _record_n(conn, 1)
    report = EvidenceVerifier(ActionRecordRepository(conn)).verify_all()
    assert report.chain_integrity and report.signature_validity
    assert report.n_records == 1


def test_verify_three_record_chain(conn: sqlite3.Connection) -> None:
    _record_n(conn, 3)
    report = EvidenceVerifier(ActionRecordRepository(conn)).verify_all()
    assert report.chain_integrity and report.signature_validity
    assert report.n_records == 3


def test_verify_detects_tampered_current_hash(conn: sqlite3.Connection) -> None:
    records = _record_n(conn, 3)
    verifier = EvidenceVerifier(ActionRecordRepository(conn))
    records[1] = records[1].model_copy(update={"current_hash": "de" * 32})
    report = verifier.verify_records(records)
    assert report.chain_integrity is False
    assert report.first_broken_at == records[1].action_id


def test_verify_detects_broken_chain(conn: sqlite3.Connection) -> None:
    records = _record_n(conn, 2)
    verifier = EvidenceVerifier(ActionRecordRepository(conn))
    records[1] = records[1].model_copy(update={"previous_hash": "WRONG"})
    report = verifier.verify_records(records)
    assert report.chain_integrity is False
    assert "previous_hash" in (report.broken_reason or "")


def test_verify_detects_invalid_signature(conn: sqlite3.Connection) -> None:
    records = _record_n(conn, 1)
    verifier = EvidenceVerifier(ActionRecordRepository(conn))
    # Keep current_hash valid but replace the signature with one for a
    # different message (valid base64, wrong signature).
    bad = records[0].model_copy(update={"signature": sign_hash("0" * 64)})
    report = verifier.verify_records([bad], anchor_previous=bad.previous_hash)
    assert report.signature_validity is False
    assert report.first_broken_at == bad.action_id


def test_verifier_works_offline(conn: sqlite3.Connection) -> None:
    # No network, no LLM: verification uses only the repo + public key.
    _record_n(conn, 2)
    report = EvidenceVerifier(ActionRecordRepository(conn)).verify_all()
    assert report.chain_integrity and report.signature_validity
