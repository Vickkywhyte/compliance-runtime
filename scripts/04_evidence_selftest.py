#!/usr/bin/env python
"""Phase 4 evidence self-test (Lesson 2, Lesson 5, ADR-004).

Hermetic: uses an in-memory DB and a temporary signing key (set_keys_dir),
so it never touches the real ~/.compliance-runtime/keys. Records 5 actions,
verifies the full chain + signatures, and checks each link by hand.
"""

from __future__ import annotations

import sys
import tempfile

from compliance_runtime.config.keys import get_or_create_signing_key, set_keys_dir
from compliance_runtime.evidence.hashing import GENESIS_HASH
from compliance_runtime.evidence.recorder import EvidenceRecorder
from compliance_runtime.evidence.signing import verify_signature
from compliance_runtime.evidence.verifier import EvidenceVerifier
from compliance_runtime.policy.models import EvaluationResult
from compliance_runtime.storage.action_records import ActionRecordRepository
from compliance_runtime.storage.db import get_connection
from compliance_runtime.storage.evaluations import EvaluationRepository
from compliance_runtime.storage.migrate import apply_migrations
from compliance_runtime.storage.models import PolicyEvaluation, ToolCall
from compliance_runtime.storage.tool_calls import ToolCallRepository
from compliance_runtime.utils.ids import new_ulid, now_utc


def _seed_and_record(conn, recorder: EvidenceRecorder, amount: int):
    call = ToolCall(
        call_id=new_ulid(), correlation_id=new_ulid(), agent_id="agent-1",
        session_id="sess-1", action="issue_refund",
        parameters={"amount": amount}, received_at=now_utc(),
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
    return recorder.record(
        call,
        EvaluationResult(
            disposition="allow", matched_rule_id="r", matched_rule_priority=1,
            reason="ok", evidence={}, policy_version="v",
            evaluated_at=now_utc(), evaluation_duration_ms=1,
        ),
        evaluation_id=eid,
    )


def main() -> int:
    passed = 0
    with tempfile.TemporaryDirectory() as tmp:
        set_keys_dir(tmp)
        try:
            get_or_create_signing_key()
            conn = get_connection(":memory:")
            apply_migrations(conn)
            repo = ActionRecordRepository(conn)
            recorder = EvidenceRecorder(repo)

            records = [_seed_and_record(conn, recorder, 100 + i) for i in range(5)]
            assert len(records) == 5
            passed += 1

            report = EvidenceVerifier(repo).verify_all()
            assert report.chain_integrity is True, report
            passed += 1
            assert report.signature_validity is True, report
            passed += 1
            assert report.n_records == 5, report
            passed += 1

            # Each link: previous_hash matches the prior current_hash.
            assert records[0].previous_hash == GENESIS_HASH
            passed += 1
            for prev, cur in zip(records, records[1:]):
                assert cur.previous_hash == prev.current_hash
            passed += 1

            # Each signature verifies.
            for record in records:
                assert verify_signature(record.current_hash, record.signature)
            passed += 1
        finally:
            set_keys_dir(None)

    print(f"PASS: all {passed} assertions passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
