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


def test_no_widget_collisions() -> None:
    """Every interactive Streamlit widget in the dashboard declares a key=.

    Streamlit derives element IDs from (widget type + args); two identical
    widgets across views collide at runtime (StreamlitDuplicateElementId).
    The mocked selftest can't catch this, so we parse the dashboard modules
    with ast and require an explicit key= on every keyed widget call.
    """
    import ast

    # Widgets that accept and need a stable key to avoid ID collisions.
    # (form_submit_button, tabs, metric, columns do not take a key.)
    keyed_widgets = {
        "number_input", "text_input", "text_area", "selectbox", "button",
        "radio", "checkbox", "slider", "multiselect", "dataframe", "form",
    }
    dashboard = Path("src/compliance_runtime/dashboard")
    violations: list[str] = []

    for path in sorted(dashboard.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr not in keyed_widgets:
                continue
            if not any(kw.arg == "key" for kw in node.keywords):
                violations.append(
                    f"{path.relative_to(dashboard)}:{node.lineno}: "
                    f".{func.attr}() missing key="
                )

    assert violations == [], "widgets missing key=:\n" + "\n".join(violations)


def test_pipeline_queryable_from_multiple_threads(tmp_path: Path) -> None:
    """A cached pipeline must be usable from a different thread (Lesson 2c).

    Real repro of the Streamlit rerun bug: build the pipeline (and its SQLite
    connection) on the main thread, then query it from a spawned thread. With
    ``check_same_thread=False`` this must not raise ``sqlite3.ProgrammingError``.
    """
    import threading

    from compliance_runtime.config.keys import set_keys_dir
    from compliance_runtime.interception.models import ToolCallRequest
    from compliance_runtime.interception.pipeline import build_pipeline

    set_keys_dir(tmp_path)
    try:
        pipeline, _ = build_pipeline("configs/runtime.yaml", db_path=tmp_path / "d.db")
        pipeline.execute(ToolCallRequest(
            action="issue_refund", parameters={"amount": 250},
            agent_id="a", session_id="s",
        ))
        # Main thread works.
        assert len(pipeline.all_action_records()) == 1

        captured: dict[str, object] = {}

        def worker() -> None:
            try:
                captured["count"] = len(pipeline.all_action_records())
            except Exception as exc:  # noqa: BLE001 - surface in the assert below
                captured["error"] = exc

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()

        assert "error" not in captured, f"cross-thread query raised {captured.get('error')!r}"
        assert captured["count"] == 1
        pipeline.close()
    finally:
        set_keys_dir(None)


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
