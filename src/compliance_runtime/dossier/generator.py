"""Compliance dossier generator (FR-6; C-38, C-39, C-40).

Builds a :class:`DossierReport` summary and renders it to an **uncompressed**
PDF (so field-whitelist audits can inspect the text). Per-action rows expose
only the whitelisted fields taken straight from the stored ``ActionRecord``;
raw parameters are never stored (C-37) and never appear, the private key is
never included (C-39), and only the public-key fingerprint is shown (C-40).
"""

from __future__ import annotations

import textwrap
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from compliance_runtime.dossier.ai_act_mapping import AiactObligation, get_obligations
from compliance_runtime.evidence.signing import get_key_id
from compliance_runtime.evidence.verifier import EvidenceVerifier
from compliance_runtime.policy.models import PolicySet
from compliance_runtime.storage.action_records import ActionRecordRepository
from compliance_runtime.storage.approvals import (
    ApprovalDecisionRepository,
    ApprovalRequestRepository,
)
from compliance_runtime.storage.audit import AuditRepository
from compliance_runtime.storage.evaluations import EvaluationRepository
from compliance_runtime.storage.models import ActionRecord
from compliance_runtime.utils.ids import now_utc

_DISPOSITIONS = ("allow", "deny", "require_approval", "allow_with_flag")
_APPROVAL_STATES = ("approved", "denied", "modified_approved", "expired", "pending")

# Per-action fields allowed in the dossier (C-38). This is the maximum set;
# a subset is fine. parameters_hash, full signature, and raw parameters are
# deliberately excluded.
WHITELISTED_ACTION_FIELDS = (
    "action_id", "disposition", "agent_id", "timestamp", "matched_rule_id",
    "previous_hash", "current_hash", "signing_key_id",
)
_HASH_TRUNC = 16


class DossierReport(BaseModel):
    """Structured summary used to render the PDF and to assert correctness."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    since: datetime | None
    until: datetime | None
    runtime_version: str
    policy_name: str
    policy_version: str
    policy_content_hash: str
    total_actions: int
    disposition_breakdown: dict[str, int]
    approval_summary: dict[str, int]
    chain_integrity: bool
    signature_validity: bool
    n_records_verified: int
    verification_key_fingerprint: str
    obligations: list[AiactObligation]
    obligation_status: dict[str, str]


class DossierGenerator:
    """Builds and writes a compliance dossier PDF."""

    def __init__(
        self,
        action_repo: ActionRecordRepository,
        approval_repo: ApprovalRequestRepository,
        decision_repo: ApprovalDecisionRepository,
        audit_repo: AuditRepository,
        evaluation_repo: EvaluationRepository,
        verifier: EvidenceVerifier,
        policy_set: PolicySet,
        runtime_version: str,
    ) -> None:
        self._actions = action_repo
        self._approvals = approval_repo
        self._decisions = decision_repo
        self._audit = audit_repo
        self._evaluations = evaluation_repo
        self._verifier = verifier
        self._policy_set = policy_set
        self._runtime_version = runtime_version

    def generate(
        self,
        output_path: Path,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> DossierReport:
        """Build the report, verify the chain, and write the PDF."""
        records = [
            r for r in self._actions.list_all()
            if (since is None or r.timestamp >= since)
            and (until is None or r.timestamp <= until)
        ]

        breakdown = {d: 0 for d in _DISPOSITIONS}
        for disposition, count in Counter(r.disposition for r in records).items():
            breakdown[disposition] = count

        # matched_rule_id lives on PolicyEvaluation; join per action (C-38
        # whitelisted field).
        matched_rules: dict[str, str | None] = {}
        for record in records:
            evaluation = self._evaluations.get_by_id(record.evaluation_id)
            matched_rules[record.action_id] = (
                evaluation.matched_rule_id if evaluation else None
            )

        # Approval summary respects the same [since, until] range as actions.
        approvals = {state: 0 for state in _APPROVAL_STATES}
        for request in self._approvals.list_in_range(since, until):
            if request.state in approvals:
                approvals[request.state] += 1

        verification = self._verifier.verify_all()
        policy = self._policy_set.policies[0] if self._policy_set.policies else None

        report = DossierReport(
            generated_at=now_utc(),
            since=since,
            until=until,
            runtime_version=self._runtime_version,
            policy_name=policy.name if policy else "unknown",
            policy_version=policy.version if policy else "unknown",
            policy_content_hash=self._policy_set.content_hash,
            total_actions=len(records),
            disposition_breakdown=breakdown,
            approval_summary=approvals,
            chain_integrity=verification.chain_integrity,
            signature_validity=verification.signature_validity,
            n_records_verified=verification.n_records,
            verification_key_fingerprint=get_key_id(),
            obligations=get_obligations(),
            obligation_status=self._obligation_status(verification),
        )
        self._render_pdf(report, records, matched_rules, Path(output_path))
        return report

    @staticmethod
    def _obligation_status(verification: Any) -> dict[str, str]:
        chain_ok = verification.chain_integrity and verification.signature_validity
        logging_status = "satisfied" if chain_ok else "degraded"
        return {
            "art12.1": logging_status,
            "art12.2": logging_status,
            "art12.3": "satisfied",  # append-only persistence (C-10)
            "art14-human-oversight": "satisfied",  # approval workflow present
        }

    def _render_pdf(
        self,
        report: DossierReport,
        records: list[ActionRecord],
        matched_rules: dict[str, str | None],
        output_path: Path,
    ) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # pageCompression=0 keeps text uncompressed so export-safety audits
        # can inspect the raw PDF bytes.
        pdf = canvas.Canvas(str(output_path), pagesize=LETTER, pageCompression=0)
        width, height = LETTER
        margin = 54
        cursor = {"y": height - margin}

        def line(text: str, size: int = 10, dy: int = 14, font: str = "Helvetica") -> None:
            if cursor["y"] < margin:
                pdf.showPage()
                cursor["y"] = height - margin
            pdf.setFont(font, size)
            pdf.drawString(margin, cursor["y"], text)
            cursor["y"] -= dy

        def wrapped(text: str, size: int = 10, dy: int = 12, width_chars: int = 95) -> None:
            for chunk in textwrap.wrap(text, width=width_chars) or [""]:
                line(chunk, size=size, dy=dy)

        line("AI Compliance Dossier", size=18, dy=24, font="Helvetica-Bold")
        line(f"generated_at: {report.generated_at.isoformat()}")
        line(f"runtime_version: {report.runtime_version}")
        line(f"range: {report.since} .. {report.until}")
        line("")

        line("Policy", size=13, dy=18, font="Helvetica-Bold")
        line(f"policy_name: {report.policy_name}")
        line(f"policy_version: {report.policy_version}")
        line(f"policy_content_hash: {report.policy_content_hash}")
        line("")

        line("Actions", size=13, dy=18, font="Helvetica-Bold")
        line(f"total_actions: {report.total_actions}")
        for disposition in _DISPOSITIONS:
            line(f"  {disposition}: {report.disposition_breakdown[disposition]}")
        line("")

        line("Human oversight", size=13, dy=18, font="Helvetica-Bold")
        for state in _APPROVAL_STATES:
            line(f"  {state}: {report.approval_summary[state]}")
        line("")

        line("Evidence verification", size=13, dy=18, font="Helvetica-Bold")
        line(f"chain_integrity: {report.chain_integrity}")
        line(f"signature_validity: {report.signature_validity}")
        line(f"n_records_verified: {report.n_records_verified}")
        line("verification_key_fingerprint (public key, not key material):")
        line(f"  {report.verification_key_fingerprint}")
        line("")

        line("EU AI Act Article 12 obligations", size=13, dy=18,
             font="Helvetica-Bold")
        for obligation in report.obligations:
            status = report.obligation_status.get(obligation.id, "unverified")
            line(f"[{obligation.id}] status={status}", font="Helvetica-Bold")
            wrapped(f"    {obligation.description}")
            wrapped(f"    artifact: {obligation.artifact}")
            wrapped(f"    verification: {obligation.verification}")
            line("")

        line("Action records (whitelisted fields only)", size=13, dy=18,
             font="Helvetica-Bold")
        for record in records:
            line(
                f"action_id={record.action_id[:_HASH_TRUNC]} "
                f"disposition={record.disposition} agent_id={record.agent_id}"
            )
            line(
                f"    matched_rule_id={matched_rules.get(record.action_id)} "
                f"timestamp={record.timestamp.isoformat()} "
                f"signing_key_id={record.signing_key_id}"
            )
            line(
                f"    previous_hash={record.previous_hash[:_HASH_TRUNC]} "
                f"current_hash={record.current_hash[:_HASH_TRUNC]}"
            )

        pdf.showPage()
        pdf.save()


def _self_test() -> None:
    """Build a dossier from a hermetic pipeline run and assert key invariants."""
    import tempfile

    from compliance_runtime import __version__
    from compliance_runtime.config.keys import set_keys_dir
    from compliance_runtime.interception.models import ToolCallRequest
    from compliance_runtime.interception.pipeline import build_pipeline

    try:
        with tempfile.TemporaryDirectory() as tmp:
            set_keys_dir(tmp)
            pipeline, conn = build_pipeline("configs/runtime.yaml", db_path=f"{tmp}/d.db")
            pipeline.execute(ToolCallRequest(action="issue_refund",
                             parameters={"amount": 250}, agent_id="a",
                             session_id="s"))
            from compliance_runtime.storage.evaluations import EvaluationRepository

            generator = DossierGenerator(
                ActionRecordRepository(conn), ApprovalRequestRepository(conn),
                ApprovalDecisionRepository(conn), AuditRepository(conn),
                EvaluationRepository(conn),
                EvidenceVerifier(ActionRecordRepository(conn)),
                pipeline._engine._policy_set, __version__,
            )
            out = Path(tmp) / "d.pdf"
            report = generator.generate(out)
            assert out.read_bytes().startswith(b"%PDF")
            assert report.chain_integrity and report.signature_validity
            pipeline.close()
    finally:
        set_keys_dir(None)
    print("dossier.generator self-test: PASS")


if __name__ == "__main__":
    _self_test()
