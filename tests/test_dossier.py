"""Tests for the dossier generator (FR-6; C-38, C-39)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from compliance_runtime import __version__
from compliance_runtime.config.keys import set_keys_dir
from compliance_runtime.dossier.generator import (
    WHITELISTED_ACTION_FIELDS,
    DossierGenerator,
    DossierReport,
)
from compliance_runtime.evidence.verifier import EvidenceVerifier
from compliance_runtime.interception.models import ToolCallRequest
from compliance_runtime.interception.pipeline import build_pipeline
from compliance_runtime.policy.loader import load_policy_set
from compliance_runtime.storage.action_records import ActionRecordRepository
from compliance_runtime.storage.approvals import (
    ApprovalDecisionRepository,
    ApprovalRequestRepository,
)
from compliance_runtime.storage.audit import AuditRepository
from compliance_runtime.storage.evaluations import EvaluationRepository

_RAW_PARAM_SENTINEL = "card_number_SECRET_SENTINEL"


@pytest.fixture()
def dossier(tmp_path: Path) -> Iterator[tuple[DossierReport, bytes]]:
    set_keys_dir(tmp_path)
    try:
        pipeline, conn = build_pipeline("configs/runtime.yaml", db_path=tmp_path / "d.db")
        # One of each disposition, plus a raw-parameter sentinel that must
        # never reach the dossier.
        pipeline.execute(ToolCallRequest(action="issue_refund",
                         parameters={"amount": 250, "note": _RAW_PARAM_SENTINEL},
                         agent_id="a", session_id="s"))
        pipeline.execute(ToolCallRequest(action="issue_refund",
                         parameters={"amount": 850}, agent_id="a", session_id="s"))
        pipeline.execute(ToolCallRequest(action="issue_refund",
                         parameters={"amount": 250}, agent_id="a", session_id="s",
                         entity_context={"fraud_flags": ["x"]}))
        generator = DossierGenerator(
            ActionRecordRepository(conn), ApprovalRequestRepository(conn),
            ApprovalDecisionRepository(conn), AuditRepository(conn),
            EvaluationRepository(conn),
            EvidenceVerifier(ActionRecordRepository(conn)),
            load_policy_set(Path("configs/policies")), __version__,
        )
        out = tmp_path / "dossier.pdf"
        report = generator.generate(out)
        yield report, out.read_bytes()
        pipeline.close()
    finally:
        set_keys_dir(None)


def test_dossier_report_shape(dossier) -> None:
    report, _ = dossier
    assert isinstance(report, DossierReport)
    assert report.runtime_version == __version__
    assert report.obligations


def test_dossier_disposition_breakdown_correct(dossier) -> None:
    report, _ = dossier
    assert report.disposition_breakdown == {
        "allow": 1, "deny": 1, "require_approval": 1, "allow_with_flag": 0
    }


def test_dossier_approval_summary_correct(dossier) -> None:
    report, _ = dossier
    assert report.approval_summary["pending"] == 1


def test_dossier_chain_integrity_true(dossier) -> None:
    report, _ = dossier
    assert report.chain_integrity is True


def test_dossier_signature_validity_true(dossier) -> None:
    report, _ = dossier
    assert report.signature_validity is True


def test_dossier_obligation_status_all_satisfied(dossier) -> None:
    report, _ = dossier
    assert set(report.obligation_status.values()) == {"satisfied"}


def test_dossier_pdf_written_and_starts_with_pdf_magic(dossier) -> None:
    _, pdf = dossier
    assert pdf.startswith(b"%PDF")


def test_dossier_does_not_contain_private_key(dossier) -> None:
    _, pdf = dossier
    assert b"PRIVATE KEY" not in pdf


def test_dossier_does_not_contain_raw_parameters(dossier) -> None:
    _, pdf = dossier
    assert _RAW_PARAM_SENTINEL.encode() not in pdf


def test_dossier_field_whitelist(dossier) -> None:
    _, pdf = dossier
    # Forbidden (non-whitelisted) field names must not appear.
    assert b"parameters_hash" not in pdf
    # A whitelisted field label is present.
    assert b"action_id" in pdf
    assert all(
        field in WHITELISTED_ACTION_FIELDS
        for field in ("action_id", "disposition", "signing_key_id")
    )


def test_verification_key_fingerprint_is_sha256_prefix(dossier) -> None:
    report, _ = dossier
    fp = report.verification_key_fingerprint
    assert len(fp) == 16
    assert all(c in "0123456789abcdef" for c in fp)


def test_dossier_approval_summary_respects_time_range(
    tmp_path: Path, seed_action_record
) -> None:
    from datetime import timedelta

    from compliance_runtime.storage.db import get_connection
    from compliance_runtime.storage.migrate import apply_migrations
    from compliance_runtime.storage.models import ApprovalRequest
    from compliance_runtime.utils.ids import new_ulid, now_utc

    set_keys_dir(tmp_path)
    try:
        conn = get_connection(tmp_path / "d.db")
        apply_migrations(conn)
        action_id = seed_action_record(conn)
        req_repo = ApprovalRequestRepository(conn)

        base = now_utc()
        times = [base, base + timedelta(seconds=1), base + timedelta(seconds=100)]
        for when in times:
            req_repo.insert(ApprovalRequest(
                request_id=new_ulid(), action_id=action_id, call_id=new_ulid(),
                reason="r", matched_rule_id="refund_limit", severity="high",
                assignee_role="compliance_officer", ttl_seconds=900,
                created_at=when, expires_at=when + timedelta(seconds=900),
                state="pending", version=1,
            ))

        generator = DossierGenerator(
            ActionRecordRepository(conn), req_repo,
            ApprovalDecisionRepository(conn), AuditRepository(conn),
            EvaluationRepository(conn),
            EvidenceVerifier(ActionRecordRepository(conn)),
            load_policy_set(Path("configs/policies")), __version__,
        )
        report = generator.generate(
            tmp_path / "ranged.pdf",
            since=base - timedelta(seconds=1),
            until=base + timedelta(seconds=2),
        )
        # Only the first two requests (base, base+1s) fall in range.
        assert report.approval_summary["pending"] == 2
        assert sum(report.approval_summary.values()) == 2
    finally:
        set_keys_dir(None)
