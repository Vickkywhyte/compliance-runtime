#!/usr/bin/env python
"""Phase 9 dossier self-test (Lesson 2, Lesson 5; C-38, C-39).

Hermetic: temp DB + temp key dir. Runs the 3 demo scripts, generates a
dossier, and asserts the report fields, PDF validity, and export safety.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from compliance_runtime import __version__
from compliance_runtime.config.keys import set_keys_dir
from compliance_runtime.dossier.generator import DossierGenerator
from compliance_runtime.evidence.verifier import EvidenceVerifier
from compliance_runtime.interception.pipeline import build_pipeline
from compliance_runtime.interception.sdk import ToolExecutor
from compliance_runtime.mock_agent.agent import MockAgent
from compliance_runtime.policy.loader import load_policy_set
from compliance_runtime.storage.action_records import ActionRecordRepository
from compliance_runtime.storage.approvals import (
    ApprovalDecisionRepository,
    ApprovalRequestRepository,
)
from compliance_runtime.storage.audit import AuditRepository
from compliance_runtime.storage.evaluations import EvaluationRepository

_SCRIPTS = sorted(Path("data/demo/agent_scripts").glob("*.json"))


def main() -> int:
    passed = 0
    with tempfile.TemporaryDirectory() as tmp:
        set_keys_dir(tmp)
        try:
            pipeline, conn = build_pipeline("configs/runtime.yaml", db_path=f"{tmp}/d.db")
            executor = ToolExecutor(pipeline)
            for script in _SCRIPTS:
                MockAgent(script, executor).run()

            generator = DossierGenerator(
                ActionRecordRepository(conn), ApprovalRequestRepository(conn),
                ApprovalDecisionRepository(conn), AuditRepository(conn),
                EvaluationRepository(conn),
                EvidenceVerifier(ActionRecordRepository(conn)),
                load_policy_set(Path("configs/policies")), __version__,
            )
            out = Path(tmp) / "dossier.pdf"
            report = generator.generate(out)

            pdf_bytes = out.read_bytes()
            assert pdf_bytes.startswith(b"%PDF"), "not a valid PDF"
            passed += 1
            assert report.total_actions == 6, report.total_actions
            passed += 1
            assert report.chain_integrity is True, report
            passed += 1
            assert report.signature_validity is True, report
            passed += 1
            assert report.disposition_breakdown == {
                "allow": 4, "deny": 1, "require_approval": 1, "allow_with_flag": 0
            }, report.disposition_breakdown
            passed += 1
            assert report.approval_summary["pending"] == 1, report.approval_summary
            passed += 1
            for oid in ("art12.1", "art12.2", "art12.3", "art14-human-oversight"):
                assert report.obligation_status[oid] == "satisfied", oid
                passed += 1
            assert b"PRIVATE KEY" not in pdf_bytes, "private key marker in PDF"
            passed += 1

            pipeline.close()
        finally:
            set_keys_dir(None)

    print(f"PASS: all {passed} assertions passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
