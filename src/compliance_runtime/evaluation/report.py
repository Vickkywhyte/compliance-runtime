"""Rendering helpers for an :class:`EvalReport` (text / JSON / CSV)."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from compliance_runtime.evaluation.runner import EvalReport


def render_text(report: EvalReport) -> str:
    """Return a human-readable summary table of the report."""
    lines = [
        f"Evaluation {report.eval_id}",
        f"  run_at:         {report.run_at.isoformat()}",
        f"  benchmark_hash: {report.benchmark_hash[:16]}...",
        f"  n_entries:      {report.n_entries}",
        "",
        "  Metrics:",
    ]
    for name in sorted(report.aggregate_metrics):
        value = report.aggregate_metrics[name]
        ci = report.aggregate_ci.get(name)
        ci_str = f"  CI[{ci[0]:.3f}, {ci[1]:.3f}]" if ci else ""
        lines.append(f"    {name:<28} {value:>12.4f}{ci_str}")
    correct = sum(1 for e in report.per_entry if e["correct"])
    lines.append("")
    lines.append(f"  Correct dispositions: {correct}/{report.n_entries}")
    return "\n".join(lines)


def write_json(report: EvalReport, path: Path) -> None:
    """Write the report as indented JSON."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(report.model_dump_json(indent=2), encoding="utf-8")


def write_csv(report: EvalReport, path: Path) -> None:
    """Write the per-entry results as CSV."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    buffer = io.StringIO()
    fieldnames = [
        "benchmark_id", "expected_disposition", "actual_disposition",
        "matched_rule_id", "correct", "evidence_complete",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for entry in report.per_entry:
        writer.writerow({key: entry.get(key) for key in fieldnames})
    Path(path).write_text(buffer.getvalue(), encoding="utf-8")
