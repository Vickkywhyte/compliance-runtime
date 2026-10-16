"""Compliance Summary view: render the latest EvalReport (06_EVAL_SPEC §7)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from compliance_runtime.dashboard.components.approval_form import safe

_CATEGORIES: dict[str, list[str]] = {
    "Enforcement": [
        "policy_precision", "policy_recall", "false_positive_rate",
        "false_negative_rate", "policy_coverage",
    ],
    "Evidence": ["audit_completeness", "chain_integrity", "signature_validity"],
    "Oversight": [
        "approval_latency_p50_ms", "approval_latency_p95_ms", "approval_rate",
        "override_rate", "auto_deny_rate",
    ],
    "Operational": [
        "runtime_overhead_p50_ms", "policy_eval_p50_ms", "evidence_write_p50_ms",
        "cost_per_1k_actions_usd",
    ],
}
_CARD_METRICS = ["policy_precision", "policy_recall", "chain_integrity",
                 "signature_validity"]


def list_eval_runs(results_dir: Path) -> list[Path]:
    """Return eval report JSON files, newest first (pure helper)."""
    directory = Path(results_dir)
    if not directory.is_dir():
        return []
    return sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime,
                  reverse=True)


def load_eval_report(path: Path) -> dict[str, Any]:
    """Load one eval report JSON (pure helper)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _ci_half_width(report: dict[str, Any], name: str) -> float | None:
    ci = report.get("aggregate_ci", {}).get(name)
    if ci and len(ci) == 2:
        return (ci[1] - ci[0]) / 2.0
    return None


def render(results_dir: Path) -> None:
    """Render the Compliance Summary tab."""
    st.header("Compliance Summary")
    runs = list_eval_runs(results_dir)
    if not runs:
        st.info("No eval runs yet. Run `make eval-mini` first.")
        return

    labels = [p.stem for p in runs]
    chosen = st.selectbox("Eval run", labels, key="compliance_summary_run_selector")
    report = load_eval_report(runs[labels.index(chosen)])
    metrics = report.get("aggregate_metrics", {})

    st.caption(
        f"eval_id={safe(report.get('eval_id'))} · "
        f"run_at={safe(report.get('run_at'))} · "
        f"n_entries={safe(report.get('n_entries'))} · "
        f"benchmark_hash={safe(str(report.get('benchmark_hash'))[:16])}"
    )

    cards = st.columns(len(_CARD_METRICS))
    for col, name in zip(cards, _CARD_METRICS):
        value = metrics.get(name)
        half = _ci_half_width(report, name)
        delta = f"±{half:.3f}" if half is not None else None
        col.metric(name, f"{value:.4f}" if value is not None else "—", delta)

    st.subheader("All metrics")
    for category, names in _CATEGORIES.items():
        st.markdown(f"**{category}**")
        rows = [
            {"metric": name, "value": metrics.get(name),
             "ci_half_width": _ci_half_width(report, name)}
            for name in names
        ]
        st.dataframe(rows, width="stretch", key=f"compliance_summary_table_{category}")
