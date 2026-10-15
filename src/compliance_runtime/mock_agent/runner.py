"""Demo orchestrator: reset DB, run scripts, generate a dossier (FR-8).

Hermetic and fast: it does NOT launch Streamlit (that blocks the terminal).
It prints the dashboard URL and exits; the user opens the dashboard separately
with ``make serve-dashboard``. ``serve_dashboard`` is kept as a no-op flag for
backward compatibility.
"""

from __future__ import annotations

import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from compliance_runtime import __version__
from compliance_runtime.config.keys import set_keys_dir
from compliance_runtime.dossier.generator import DossierGenerator
from compliance_runtime.evidence.verifier import EvidenceVerifier
from compliance_runtime.exceptions import DemoError
from compliance_runtime.interception.pipeline import build_pipeline
from compliance_runtime.interception.sdk import ToolExecutor
from compliance_runtime.mock_agent.agent import MockAgent, StepResult
from compliance_runtime.policy.loader import load_policy_set
from compliance_runtime.storage.action_records import ActionRecordRepository
from compliance_runtime.storage.approvals import (
    ApprovalDecisionRepository,
    ApprovalRequestRepository,
)
from compliance_runtime.storage.audit import AuditRepository
from compliance_runtime.storage.evaluations import EvaluationRepository
from compliance_runtime.utils.ids import now_utc
from compliance_runtime.utils.logging import get_logger

_logger = get_logger("demo_runner")
_SCRIPT_DIR = Path("data/demo/agent_scripts")
_DASHBOARD_URL = "http://localhost:8501"


class DemoReport(BaseModel):
    """Aggregate result of a demo run."""

    model_config = ConfigDict(extra="forbid")

    scripts_run: int
    steps_executed: int
    allowances: int
    denials: int
    approvals_requested: int
    flagged: int
    dossier_path: Path
    elapsed_seconds: float


class DemoRunner:
    """Resets state, runs the demo scripts, and generates a dossier."""

    def __init__(
        self,
        db_path: Path,
        keys_dir: Path,
        config_path: Path,
        dossier_dir: Path = Path("results/dossiers"),
        script_dir: Path = _SCRIPT_DIR,
    ) -> None:
        self._db_path = Path(db_path)
        self._keys_dir = Path(keys_dir)
        self._config_path = Path(config_path)
        self._dossier_dir = Path(dossier_dir)
        self._script_dir = Path(script_dir)

    def _reset_db(self) -> None:
        for suffix in ("", "-wal", "-shm", "-journal"):
            candidate = Path(str(self._db_path) + suffix)
            if candidate.exists():
                candidate.unlink()

    def run_demo(self, *, serve_dashboard: bool = False) -> DemoReport:
        """Run all demo scripts and generate a dossier. Returns a DemoReport."""
        start = time.perf_counter()
        set_keys_dir(self._keys_dir)
        try:
            self._reset_db()
            pipeline, conn = build_pipeline(
                str(self._config_path), db_path=str(self._db_path)
            )
            executor = ToolExecutor(pipeline)

            scripts = sorted(self._script_dir.glob("*.json"))
            if not scripts:
                raise DemoError(f"no demo scripts found in {self._script_dir}")

            all_results: list[StepResult] = []
            for script in scripts:
                all_results.extend(MockAgent(script, executor).run())

            allowances = sum(1 for r in all_results if r.disposition == "allow")
            denials = sum(1 for r in all_results if r.disposition == "deny")
            approvals = sum(
                1 for r in all_results if r.disposition == "require_approval"
            )
            flagged = sum(
                1 for r in all_results if r.disposition == "allow_with_flag"
            )
            if not (allowances and denials and approvals):
                raise DemoError(
                    "demo did not exercise all dispositions: "
                    f"allow={allowances} deny={denials} approval={approvals}"
                )

            dossier_path = self._dossier_dir / f"demo_{now_utc():%Y%m%dT%H%M%S}.pdf"
            self._generate_dossier(conn, dossier_path)

            if serve_dashboard:
                _logger.info("dashboard_hint", url=_DASHBOARD_URL)

            report = DemoReport(
                scripts_run=len(scripts),
                steps_executed=len(all_results),
                allowances=allowances,
                denials=denials,
                approvals_requested=approvals,
                flagged=flagged,
                dossier_path=dossier_path,
                elapsed_seconds=time.perf_counter() - start,
            )
            pipeline.close()
            return report
        finally:
            set_keys_dir(None)

    def _generate_dossier(self, conn, dossier_path: Path) -> None:
        policy_set = load_policy_set(self._config_path.parent / "policies")
        generator = DossierGenerator(
            ActionRecordRepository(conn),
            ApprovalRequestRepository(conn),
            ApprovalDecisionRepository(conn),
            AuditRepository(conn),
            EvaluationRepository(conn),
            EvidenceVerifier(ActionRecordRepository(conn)),
            policy_set,
            __version__,
        )
        generator.generate(dossier_path)


def _self_test() -> None:
    """Run the demo end-to-end in a temp dir."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        runner = DemoRunner(
            db_path=Path(tmp) / "demo.db",
            keys_dir=Path(tmp) / "keys",
            config_path=Path("configs/runtime.yaml"),
            dossier_dir=Path(tmp) / "dossiers",
        )
        report = runner.run_demo(serve_dashboard=False)
        assert report.steps_executed == 6, report.steps_executed
        assert report.dossier_path.exists()
    print("mock_agent.runner self-test: PASS")


if __name__ == "__main__":
    _self_test()
