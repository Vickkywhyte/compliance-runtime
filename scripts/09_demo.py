#!/usr/bin/env python
"""Phase 9 demo CLI (FR-8).

Runs the three scripted demos through the runtime and generates a dossier.
Does NOT launch Streamlit (that would block the terminal); it prints the
dashboard URL so the user can open it separately with `make serve-dashboard`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from compliance_runtime.exceptions import ComplianceRuntimeError
from compliance_runtime.mock_agent.runner import DemoRunner

_DEFAULT_DB = "data/runtime.db"
_DEFAULT_KEYS = "~/.compliance-runtime/keys"
_DASHBOARD_URL = "http://localhost:8501"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the compliance-runtime demo.")
    parser.add_argument("--reset", action="store_true", default=True)
    parser.add_argument("--no-serve", action="store_true",
                        help="(no-op) the demo never launches Streamlit")
    parser.add_argument("--db", default=_DEFAULT_DB)
    parser.add_argument("--keys-dir", default=_DEFAULT_KEYS)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    runner = DemoRunner(
        db_path=Path(args.db),
        keys_dir=Path(args.keys_dir).expanduser(),
        config_path=Path("configs/runtime.yaml"),
    )
    report = runner.run_demo(serve_dashboard=False)

    print("Demo results")
    print(f"  scripts run:        {report.scripts_run}")
    print(f"  steps executed:     {report.steps_executed}")
    print(f"  allowed:            {report.allowances}")
    print(f"  denied:             {report.denials}")
    print(f"  approvals requested:{report.approvals_requested}")
    print(f"  flagged:            {report.flagged}")
    print(f"  dossier:            {report.dossier_path}")
    print(f"\nOpen the dashboard with `make serve-dashboard` -> {_DASHBOARD_URL}")
    print(f"PASS: demo completed in {report.elapsed_seconds:.1f}s")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except ComplianceRuntimeError as exc:
        print(f"demo failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
