"""Offline evidence verifier (ADR-004, 09_RUNTIME_DESIGN §7.4).

Recomputes each record's hash, checks the chain linkage, and verifies each
Ed25519 signature. Pure with respect to the record set + public key: it needs
no network and no LLM. :meth:`verify_records` is the testable core; the other
methods fetch records from the repository and delegate to it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from compliance_runtime.evidence.hashing import GENESIS_HASH, compute_current_hash
from compliance_runtime.evidence.signing import verify_signature
from compliance_runtime.storage.action_records import ActionRecordRepository
from compliance_runtime.storage.models import ActionRecord


class VerificationReport(BaseModel):
    """The result of verifying a set of records."""

    model_config = ConfigDict(extra="forbid")

    chain_integrity: bool
    signature_validity: bool
    n_records: int
    first_broken_at: str | None = None
    broken_reason: str | None = None


def _record_fields(record: ActionRecord) -> dict:
    """Return the record as the field dict used for hashing."""
    # hashing.record_hash_fields excludes previous_hash/current_hash/signature;
    # model_dump keeps timestamp as a datetime, which canonicalize handles.
    return record.model_dump()


class EvidenceVerifier:
    """Verifies hash-chain integrity and signatures for action records."""

    def __init__(self, repo: ActionRecordRepository) -> None:
        self._repo = repo

    def verify_records(
        self,
        records: list[ActionRecord],
        anchor_previous: str | None = None,
    ) -> VerificationReport:
        """Verify a list of records in order (the testable core).

        ``anchor_previous`` is the expected ``previous_hash`` of the first
        record: ``GENESIS`` for a full chain (default), or the first record's
        own recorded ``previous_hash`` when verifying a sub-range (so the link
        into the range is trusted and only internal consistency is checked).
        """
        n = len(records)
        expected_prev = anchor_previous if anchor_previous is not None else GENESIS_HASH

        for index, record in enumerate(records):
            if index > 0:
                expected_prev = records[index - 1].current_hash

            if record.previous_hash != expected_prev:
                return VerificationReport(
                    chain_integrity=False,
                    signature_validity=True,
                    n_records=n,
                    first_broken_at=record.action_id,
                    broken_reason=(
                        f"previous_hash mismatch: expected {expected_prev!r}, "
                        f"got {record.previous_hash!r}"
                    ),
                )

            recomputed = compute_current_hash(
                _record_fields(record), record.previous_hash
            )
            if recomputed != record.current_hash:
                return VerificationReport(
                    chain_integrity=False,
                    signature_validity=True,
                    n_records=n,
                    first_broken_at=record.action_id,
                    broken_reason="current_hash does not match recomputed hash",
                )

            if not verify_signature(record.current_hash, record.signature):
                return VerificationReport(
                    chain_integrity=True,
                    signature_validity=False,
                    n_records=n,
                    first_broken_at=record.action_id,
                    broken_reason="signature failed to verify",
                )

        return VerificationReport(
            chain_integrity=True, signature_validity=True, n_records=n
        )

    def verify_all(self) -> VerificationReport:
        """Verify the entire chain from GENESIS."""
        return self.verify_records(self._repo.list_all())

    def verify_one(self, action_id: str) -> VerificationReport:
        """Verify a single record's hash + signature (linkage trusted)."""
        record = self._repo.get_by_id(action_id)
        if record is None:
            return VerificationReport(
                chain_integrity=False,
                signature_validity=False,
                n_records=0,
                first_broken_at=action_id,
                broken_reason="record not found",
            )
        return self.verify_records([record], anchor_previous=record.previous_hash)

    def verify_range(self, start_id: str, end_id: str) -> VerificationReport:
        """Verify a contiguous range (link into the range is trusted)."""
        records = self._repo.list_range(start_id, end_id)
        anchor = records[0].previous_hash if records else None
        return self.verify_records(records, anchor_previous=anchor)


def _self_test() -> None:
    """Record three actions and confirm the full chain verifies."""
    import tempfile

    from compliance_runtime.config.keys import set_keys_dir
    from compliance_runtime.evidence.recorder import EvidenceRecorder
    from compliance_runtime.policy.models import EvaluationResult
    from compliance_runtime.storage.db import get_connection
    from compliance_runtime.storage.migrate import apply_migrations
    from compliance_runtime.storage.evaluations import EvaluationRepository
    from compliance_runtime.storage.models import PolicyEvaluation, ToolCall
    from compliance_runtime.storage.tool_calls import ToolCallRepository
    from compliance_runtime.utils.ids import new_ulid, now_utc

    try:
        with tempfile.TemporaryDirectory() as tmp:
            set_keys_dir(tmp)
            conn = get_connection(":memory:")
            apply_migrations(conn)
            repo = ActionRecordRepository(conn)
            recorder = EvidenceRecorder(repo)
            for _ in range(3):
                call = ToolCall(
                    call_id=new_ulid(), correlation_id=new_ulid(), agent_id="a",
                    session_id="s", action="issue_refund",
                    parameters={"amount": 100}, received_at=now_utc(),
                )
                ToolCallRepository(conn).insert(call)
                eid = new_ulid()
                EvaluationRepository(conn).insert(
                    PolicyEvaluation(
                        evaluation_id=eid, call_id=call.call_id,
                        matched_rule_id="r", matched_rule_priority=1,
                        policy_version="v", disposition="allow", reason="ok",
                        evidence={}, evaluated_at=now_utc(),
                        evaluation_duration_ms=1,
                    )
                )
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
            report = EvidenceVerifier(repo).verify_all()
            assert report.chain_integrity and report.signature_validity
            assert report.n_records == 3
    finally:
        set_keys_dir(None)
    print("evidence.verifier self-test: PASS")


if __name__ == "__main__":
    _self_test()
