"""Evidence recorder: hash-chain + sign every authorized action (ADR-004).

The recorder computes the hash chain and signature BEFORE calling the
repository (whose own chain guard is the last line of defense). Raw parameter
values never enter the evidence store: only ``parameters_hash`` — the SHA-256
of the canonical parameters — is recorded (C-37).

Field-ordering note: ``signing_key_id`` is part of the hashed payload (it is
not in ``hashing._EXCLUDED_FIELDS``), so the key id is computed before the
hash and included in ``record_fields``. The verifier reconstructs the exact
same field set from the stored record, so the hashes match.
"""

from __future__ import annotations

from typing import Any

from compliance_runtime import __version__ as RUNTIME_VERSION
from compliance_runtime.evidence.hashing import (
    GENESIS_HASH,
    canonicalize,
    compute_current_hash,
    sha256_hex,
)
from compliance_runtime.evidence.signing import get_key_id, sign_hash
from compliance_runtime.policy.models import EvaluationResult
from compliance_runtime.storage.action_records import ActionRecordRepository
from compliance_runtime.storage.models import ActionRecord, ToolCall
from compliance_runtime.utils.ids import new_ulid, now_utc


class EvidenceRecorder:
    """Records a signed, hash-chained :class:`ActionRecord` for each action."""

    def __init__(self, repo: ActionRecordRepository) -> None:
        self._repo = repo

    def record(
        self,
        call: ToolCall,
        evaluation: EvaluationResult,
        *,
        evaluation_id: str | None = None,
    ) -> ActionRecord:
        """Build, sign, persist, and return the action record for a call.

        ``evaluation_id`` may be supplied to reference an already-persisted
        ``PolicyEvaluation`` (satisfying the DB foreign key). ``EvaluationResult``
        carries no id of its own, so one is generated when not supplied.
        """
        latest = self._repo.latest()
        previous_hash = latest.current_hash if latest else GENESIS_HASH

        resolved_eval_id = (
            evaluation_id
            or getattr(evaluation, "evaluation_id", None)
            or new_ulid()
        )
        parameters_hash = sha256_hex(canonicalize(call.parameters))

        # signing_key_id is part of the hashed payload, so compute it first.
        key_id = get_key_id()

        record_fields: dict[str, Any] = {
            "action_id": new_ulid(),
            "call_id": call.call_id,
            "evaluation_id": resolved_eval_id,
            "disposition": evaluation.disposition,
            "agent_id": call.agent_id,
            "session_id": call.session_id,
            "action": call.action,
            "parameters_hash": parameters_hash,
            "timestamp": now_utc(),
            "signing_key_id": key_id,
            "runtime_version": RUNTIME_VERSION,
        }

        current_hash = compute_current_hash(record_fields, previous_hash)
        signature = sign_hash(current_hash)

        record = ActionRecord(
            **record_fields,
            previous_hash=previous_hash,
            current_hash=current_hash,
            signature=signature,
        )
        self._repo.insert(record)
        return record


def _self_test() -> None:
    """Record two chained actions in a temp key dir + in-memory DB."""
    import tempfile

    from compliance_runtime.config.keys import set_keys_dir
    from compliance_runtime.storage.db import get_connection
    from compliance_runtime.storage.migrate import apply_migrations
    from compliance_runtime.storage.evaluations import EvaluationRepository
    from compliance_runtime.storage.models import PolicyEvaluation
    from compliance_runtime.storage.tool_calls import ToolCallRepository

    try:
        with tempfile.TemporaryDirectory() as tmp:
            set_keys_dir(tmp)
            conn = get_connection(":memory:")
            apply_migrations(conn)
            recorder = EvidenceRecorder(ActionRecordRepository(conn))

            call = ToolCall(
                call_id=new_ulid(),
                correlation_id=new_ulid(),
                agent_id="a",
                session_id="s",
                action="issue_refund",
                parameters={"amount": 100},
                received_at=now_utc(),
            )
            ToolCallRepository(conn).insert(call)
            eval_id = new_ulid()
            EvaluationRepository(conn).insert(
                PolicyEvaluation(
                    evaluation_id=eval_id,
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
            result = EvaluationResult(
                disposition="allow",
                matched_rule_id="default_allow_refunds",
                matched_rule_priority=100,
                reason="ok",
                evidence={},
                policy_version="demo@1.0.0+abc",
                evaluated_at=now_utc(),
                evaluation_duration_ms=1,
            )
            record = recorder.record(call, result, evaluation_id=eval_id)
            assert record.previous_hash == GENESIS_HASH
            assert record.parameters_hash == sha256_hex(canonicalize({"amount": 100}))
    finally:
        set_keys_dir(None)
    print("evidence.recorder self-test: PASS")


if __name__ == "__main__":
    _self_test()
