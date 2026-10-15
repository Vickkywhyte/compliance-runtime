"""Tests for the mock agent (ADR-006)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from compliance_runtime.config.keys import set_keys_dir
from compliance_runtime.exceptions import DemoError
from compliance_runtime.interception.sdk import ToolExecutor
from compliance_runtime.mock_agent.agent import MockAgent, StepResult

_DEMO_001 = Path("data/demo/agent_scripts/demo_001.json")
_DEMO_003 = Path("data/demo/agent_scripts/demo_003.json")


@pytest.fixture()
def executor_factory(tmp_path: Path) -> Iterator[Callable[[], ToolExecutor]]:
    set_keys_dir(tmp_path)
    created: list[ToolExecutor] = []

    def make() -> ToolExecutor:
        ex = ToolExecutor.from_config(
            "configs/runtime.yaml", db_path=tmp_path / f"db_{len(created)}.db"
        )
        created.append(ex)
        return ex

    try:
        yield make
    finally:
        for ex in created:
            ex.close()
        set_keys_dir(None)


def test_mock_agent_reads_script(executor_factory) -> None:
    agent = MockAgent(_DEMO_001, executor_factory())
    assert agent.name == "demo_001_happy_path"


def test_mock_agent_runs_all_steps(executor_factory) -> None:
    results = MockAgent(_DEMO_001, executor_factory()).run()
    assert len(results) == 2


def test_mock_agent_captures_dispositions(executor_factory) -> None:
    results = MockAgent(_DEMO_003, executor_factory()).run()
    assert results[0].disposition == "allow"
    assert results[1].disposition == "deny"


def test_mock_agent_step_result_shape(executor_factory) -> None:
    result = MockAgent(_DEMO_001, executor_factory()).run()[0]
    assert isinstance(result, StepResult)
    assert result.step_index == 0
    assert result.action == "issue_refund"


def test_mock_agent_deterministic(executor_factory) -> None:
    first = [r.disposition for r in MockAgent(_DEMO_003, executor_factory()).run()]
    second = [r.disposition for r in MockAgent(_DEMO_003, executor_factory()).run()]
    assert first == second


def test_mock_agent_missing_script_raises(executor_factory) -> None:
    with pytest.raises(DemoError):
        MockAgent(Path("data/demo/agent_scripts/nope.json"), executor_factory())


def test_mock_agent_malformed_script_raises(executor_factory, tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(DemoError):
        MockAgent(bad, executor_factory())
