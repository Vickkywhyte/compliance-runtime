"""Export-safety tests for the dossier (T-08; C-38, C-39, C-40)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from compliance_runtime import __version__
from compliance_runtime.config.keys import set_keys_dir
from compliance_runtime.dossier.generator import DossierGenerator
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

_PARAM_SENTINEL = "card_number_0000_SENTINEL"


@pytest.fixture()
def dossier_bytes(tmp_path: Path) -> Iterator[tuple[bytes, str, str]]:
    set_keys_dir(tmp_path)
    try:
        pipeline, conn = build_pipeline("configs/runtime.yaml", db_path=tmp_path / "d.db")
        pipeline.execute(ToolCallRequest(
            action="issue_refund",
            parameters={"amount": 250, "card_number": _PARAM_SENTINEL},
            agent_id="a", session_id="s"))
        action_repo = ActionRecordRepository(conn)
        generator = DossierGenerator(
            action_repo, ApprovalRequestRepository(conn),
            ApprovalDecisionRepository(conn), AuditRepository(conn),
            EvaluationRepository(conn),
            EvidenceVerifier(action_repo),
            load_policy_set(Path("configs/policies")), __version__,
        )
        out = tmp_path / "d.pdf"
        report = generator.generate(out)
        record = action_repo.list_all()[0]
        yield out.read_bytes(), report.verification_key_fingerprint, record.signature
        pipeline.close()
    finally:
        set_keys_dir(None)


def test_dossier_does_not_contain_private_key_pem(dossier_bytes) -> None:
    pdf, _, _ = dossier_bytes
    assert b"-----BEGIN PRIVATE KEY-----" not in pdf
    assert b"PRIVATE KEY" not in pdf


def test_dossier_does_not_contain_raw_parameters(dossier_bytes) -> None:
    pdf, _, _ = dossier_bytes
    assert _PARAM_SENTINEL.encode() not in pdf
    assert b"card_number" not in pdf


def test_dossier_includes_verification_key_fingerprint(dossier_bytes) -> None:
    pdf, fingerprint, _ = dossier_bytes
    assert fingerprint.encode() in pdf


def test_dossier_field_whitelist_enforced(dossier_bytes) -> None:
    pdf, _, _ = dossier_bytes
    assert b"parameters_hash" not in pdf


def test_dossier_does_not_include_signature_full(dossier_bytes) -> None:
    pdf, _, signature = dossier_bytes
    # The full base64 signature must not be embedded in the export.
    assert signature.encode() not in pdf


def test_dossier_does_not_include_parameters_hash(dossier_bytes) -> None:
    pdf, _, _ = dossier_bytes
    assert b"parameters_hash" not in pdf
