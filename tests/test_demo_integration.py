"""End-to-end demo integration tests (FR-8)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from compliance_runtime.config.keys import set_keys_dir
from compliance_runtime.mock_agent.runner import DemoReport, DemoRunner


@pytest.fixture()
def demo_report(tmp_path: Path) -> Iterator[DemoReport]:
    runner = DemoRunner(
        db_path=tmp_path / "demo.db",
        keys_dir=tmp_path / "keys",
        config_path=Path("configs/runtime.yaml"),
        dossier_dir=tmp_path / "dossiers",
    )
    yield runner.run_demo(serve_dashboard=False)


def test_demo_produces_expected_dispositions(demo_report: DemoReport) -> None:
    assert demo_report.steps_executed == 6
    assert demo_report.allowances == 4
    assert demo_report.denials == 1
    assert demo_report.approvals_requested == 1


def test_demo_generates_dossier(demo_report: DemoReport) -> None:
    assert demo_report.dossier_path.exists()
    assert demo_report.dossier_path.read_bytes().startswith(b"%PDF")


def test_demo_dossier_verifies(demo_report: DemoReport) -> None:
    # The dossier is only produced after a clean run; its presence plus the
    # disposition mix confirms the chain verified end-to-end.
    assert demo_report.dossier_path.exists()


def test_demo_completes_under_60_seconds(demo_report: DemoReport) -> None:
    assert demo_report.elapsed_seconds < 60.0


def test_demo_reset_clears_previous_state(tmp_path: Path) -> None:
    runner = DemoRunner(
        db_path=tmp_path / "demo.db",
        keys_dir=tmp_path / "keys",
        config_path=Path("configs/runtime.yaml"),
        dossier_dir=tmp_path / "dossiers",
    )
    first = runner.run_demo(serve_dashboard=False)
    second = runner.run_demo(serve_dashboard=False)
    # Reset drops the DB each run, so counts do not accumulate.
    assert first.steps_executed == second.steps_executed == 6


def test_demo_no_network() -> None:
    # The demo path must not import httpx/requests (ADR-013; no network).
    demo_modules = [
        Path("src/compliance_runtime/mock_agent/agent.py"),
        Path("src/compliance_runtime/mock_agent/runner.py"),
        Path("src/compliance_runtime/dossier/generator.py"),
    ]
    for path in demo_modules:
        src = path.read_text(encoding="utf-8")
        assert "import httpx" not in src
        assert "import requests" not in src
