#!/usr/bin/env python
"""Phase 6 runtime pipeline self-test (Lesson 2, Lesson 3, ADR-013).

Hermetic: in-memory-equivalent file DB in a tempdir + temporary signing key.
Runs the three canonical scenarios through the full pipeline, then verifies
the evidence chain and the audit trail.
"""

from __future__ import annotations

import sys
import tempfile

from compliance_runtime.config.keys import set_keys_dir
from compliance_runtime.interception.models import ToolCallRequest
from compliance_runtime.interception.pipeline import build_pipeline


def main() -> int:
    passed = 0
    with tempfile.TemporaryDirectory() as tmp:
        set_keys_dir(tmp)
        try:
            pipeline, conn = build_pipeline(
                "configs/runtime.yaml", db_path=f"{tmp}/runtime.db"
            )

            allow = pipeline.execute(
                ToolCallRequest(action="issue_refund",
                                parameters={"amount": 250, "currency": "EUR"},
                                agent_id="a", session_id="s")
            )
            assert allow.disposition == "allow", allow.disposition
            assert allow.success is True and allow.result == {"status": "allowed"}
            passed += 1

            approval = pipeline.execute(
                ToolCallRequest(action="issue_refund",
                                parameters={"amount": 850, "currency": "EUR"},
                                agent_id="a", session_id="s")
            )
            assert approval.disposition == "require_approval", approval.disposition
            assert approval.status == "pending" and approval.request_id
            assert approval.expires_at is not None
            passed += 1

            deny = pipeline.execute(
                ToolCallRequest(action="issue_refund",
                                parameters={"amount": 250, "currency": "EUR"},
                                agent_id="a", session_id="s",
                                entity_context={"fraud_flags": ["chargeback_risk"]})
            )
            assert deny.disposition == "deny", deny.disposition
            assert deny.success is False and deny.error["code"] == "POLICY_DENIED"
            passed += 1

            report = pipeline.verify_chain()
            assert report.n_records == 3, report.n_records
            passed += 1
            assert report.chain_integrity and report.signature_validity, report
            passed += 1

            # The approval produced an audit trail.
            chain = pipeline._approvals.audit_chain_for_request(approval.request_id)
            assert [e.action for e in chain] == ["approval_requested"], chain
            passed += 1

            pipeline.close()
        finally:
            set_keys_dir(None)

    print(f"PASS: all {passed} assertions passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
