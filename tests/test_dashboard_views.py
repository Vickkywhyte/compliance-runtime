"""Tests for dashboard components and views (C-06, ADR-007)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from compliance_runtime.dashboard.components import (
    chain_viewer,
    disposition_badge,
    policy_info,
)
from compliance_runtime.dashboard.components.approval_form import safe
from compliance_runtime.dashboard.views import compliance_summary
from compliance_runtime.policy.loader import load_policy_set

_POLICY = load_policy_set(Path("configs/policies"))


def test_disposition_badge_renders(monkeypatch) -> None:
    mock_st = MagicMock()
    monkeypatch.setattr(disposition_badge, "st", mock_st)
    disposition_badge.render_disposition_badge("allow")
    assert mock_st.markdown.called


def test_severity_badge_renders(monkeypatch) -> None:
    mock_st = MagicMock()
    monkeypatch.setattr(disposition_badge, "st", mock_st)
    disposition_badge.render_severity_badge("high")
    assert mock_st.markdown.called


def test_safe_escapes_html() -> None:
    assert safe("<script>alert(1)</script>") == (
        "&lt;script&gt;alert(1)&lt;/script&gt;"
    )


def test_safe_preserves_plain_text() -> None:
    assert safe("issue_refund 250 EUR") == "issue_refund 250 EUR"


def test_approval_form_uses_pipeline() -> None:
    # Import-graph guard (C-13 equivalent): the approval-path modules must not
    # reference the repositories directly, and must call decide_approval.
    form_src = Path(
        "src/compliance_runtime/dashboard/components/approval_form.py"
    ).read_text(encoding="utf-8")
    view_src = Path(
        "src/compliance_runtime/dashboard/views/approvals.py"
    ).read_text(encoding="utf-8")
    for src in (form_src, view_src):
        assert "ApprovalRequestRepository" not in src
        assert "ApprovalDecisionRepository" not in src
    assert "decide_approval" in form_src


def test_chain_viewer_truncates_hashes() -> None:
    assert chain_viewer.trunc("a" * 64, 12) == "a" * 12
    assert chain_viewer.trunc("short", 12) == "short"


def test_policy_info_shows_content_hash(monkeypatch) -> None:
    mock_st = MagicMock()
    monkeypatch.setattr(policy_info, "st", mock_st)
    policy_info.render_policy_info(_POLICY)
    # The full content hash is passed to st.code.
    coded = [call.args[0] for call in mock_st.code.call_args_list]
    assert _POLICY.content_hash in coded


def test_compliance_summary_reads_eval_files(tmp_path: Path) -> None:
    report = {
        "eval_id": "r1", "run_at": "2026-10-15T00:00:00+00:00",
        "benchmark_hash": "h", "n_entries": 3,
        "aggregate_metrics": {"policy_precision": 1.0},
        "aggregate_ci": {}, "per_entry": [],
    }
    (tmp_path / "r1.json").write_text(json.dumps(report), encoding="utf-8")
    runs = compliance_summary.list_eval_runs(tmp_path)
    assert len(runs) == 1
    loaded = compliance_summary.load_eval_report(runs[0])
    assert loaded["aggregate_metrics"]["policy_precision"] == 1.0
