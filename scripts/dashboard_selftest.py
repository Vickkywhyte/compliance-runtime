#!/usr/bin/env python
"""Phase 8 dashboard self-test (Lesson 2).

Exercises every view and component render function headless: a fake Streamlit
module (injected before import) captures all ``st.*`` calls, and the render
functions run against a real in-memory pipeline seeded with one of each
disposition. Does NOT launch Streamlit. Exits non-zero on any exception.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock


def _install_fake_streamlit() -> MagicMock:
    """Inject a MagicMock 'streamlit' configured for headless render calls."""
    fake = MagicMock(name="streamlit")
    fake.columns.side_effect = lambda spec, **k: [
        MagicMock() for _ in range(spec if isinstance(spec, int) else len(spec))
    ]
    fake.tabs.side_effect = lambda labels, **k: [MagicMock() for _ in labels]
    # Pick the first option so list views short-circuit on "(none)" while the
    # summary view selects a real run.
    fake.selectbox.side_effect = lambda label, options, **k: (
        options[0] if options else None
    )
    fake.button.return_value = False
    fake.form_submit_button.return_value = False
    fake.number_input.return_value = 0
    fake.text_input.return_value = ""
    fake.text_area.return_value = ""
    sys.modules["streamlit"] = fake
    return fake


def _fake_report() -> dict:
    metrics = {
        name: 1.0
        for name in (
            "policy_precision", "policy_recall", "false_positive_rate",
            "false_negative_rate", "policy_coverage", "audit_completeness",
            "chain_integrity", "signature_validity", "approval_latency_p50_ms",
            "approval_latency_p95_ms", "approval_rate", "override_rate",
            "auto_deny_rate", "runtime_overhead_p50_ms", "policy_eval_p50_ms",
            "evidence_write_p50_ms", "cost_per_1k_actions_usd",
        )
    }
    return {
        "eval_id": "20261015T000000_eval", "run_at": "2026-10-15T00:00:00+00:00",
        "benchmark_hash": "abc123", "n_entries": 3,
        "aggregate_metrics": metrics,
        "aggregate_ci": {"policy_coverage": [0.9, 1.0]},
        "per_entry": [],
    }


def main() -> int:
    _install_fake_streamlit()

    # Imports that touch streamlit must happen AFTER the fake is installed.
    from compliance_runtime.config.keys import set_keys_dir
    from compliance_runtime.dashboard.components import (
        approval_form,
        chain_viewer,
        disposition_badge,
        policy_info,
    )
    from compliance_runtime.dashboard.views import (
        approvals,
        compliance_summary,
        evidence_chain,
        live_actions,
    )
    from compliance_runtime.interception.models import ToolCallRequest
    from compliance_runtime.interception.pipeline import build_pipeline

    passed = 0
    with tempfile.TemporaryDirectory() as tmp:
        set_keys_dir(tmp)
        try:
            pipeline, _ = build_pipeline("configs/runtime.yaml", db_path=f"{tmp}/d.db")

            pipeline.execute(ToolCallRequest(action="issue_refund",
                             parameters={"amount": 250}, agent_id="a",
                             session_id="s"))
            approval = pipeline.execute(ToolCallRequest(action="issue_refund",
                                        parameters={"amount": 850}, agent_id="a",
                                        session_id="s"))
            pipeline.execute(ToolCallRequest(action="issue_refund",
                             parameters={"amount": 250}, agent_id="a",
                             session_id="s",
                             entity_context={"fraud_flags": ["x"]}))

            results_dir = Path(tmp) / "evals"
            results_dir.mkdir()
            (results_dir / "run.json").write_text(json.dumps(_fake_report()),
                                                  encoding="utf-8")

            policy_set = pipeline._engine._policy_set
            records = pipeline.all_action_records()

            # Views.
            live_actions.render(pipeline); passed += 1
            approvals.render(pipeline, "compliance_officer"); passed += 1
            evidence_chain.render(pipeline); passed += 1
            compliance_summary.render(results_dir); passed += 1

            # Components.
            disposition_badge.render_disposition_badge("allow"); passed += 1
            disposition_badge.render_severity_badge("high"); passed += 1
            policy_info.render_policy_info(policy_set); passed += 1
            approval_form.render_approval_actions(
                pipeline, approval.request_id, "compliance_officer"); passed += 1
            chain_viewer.render_record(records[0]); passed += 1
            chain_viewer.render_verification(pipeline.verify_chain()); passed += 1
            chain_viewer.render_chain_table(records, 0, 50); passed += 1

            pipeline.close()
        finally:
            set_keys_dir(None)

    print(f"PASS: all {passed} assertions passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
