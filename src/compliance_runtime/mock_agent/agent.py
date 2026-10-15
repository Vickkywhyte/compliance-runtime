"""The mock agent: replays scripted tool calls through the runtime (ADR-006)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from compliance_runtime.exceptions import DemoError
from compliance_runtime.interception.sdk import ToolExecutor
from compliance_runtime.storage.models import Disposition
from compliance_runtime.utils.logging import get_logger

_logger = get_logger("mock_agent")


class StepResult(BaseModel):
    """The outcome of one scripted step."""

    model_config = ConfigDict(extra="forbid")

    step_index: int
    action: str
    parameters: dict[str, Any]
    disposition: Disposition
    success: bool | None
    reason: str
    matched_rule_id: str | None
    request_id: str | None


class MockAgent:
    """Executes a scripted sequence of tool calls via a :class:`ToolExecutor`."""

    def __init__(self, script_path: Path, executor: ToolExecutor) -> None:
        self._script_path = Path(script_path)
        self._executor = executor
        self._script = self._load_script(self._script_path)

    @staticmethod
    def _load_script(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise DemoError(f"agent script not found: {path}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DemoError(f"malformed agent script {path}: {exc}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("steps"), list):
            raise DemoError(f"agent script {path} must have a 'steps' list")
        return data

    @property
    def name(self) -> str:
        """The script's name."""
        return self._script.get("name", self._script_path.stem)

    def run(self) -> list[StepResult]:
        """Execute every step and return the per-step results."""
        results: list[StepResult] = []
        for index, step in enumerate(self._script["steps"]):
            response = self._executor.execute(
                action=step["action"],
                parameters=step["parameters"],
                agent_id=self.name,
                session_id=self.name,
                entity_context=step.get("entity_context"),
            )
            result = StepResult(
                step_index=index,
                action=step["action"],
                parameters=step["parameters"],
                disposition=response.disposition,
                success=response.success,
                reason=response.reason,
                matched_rule_id=response.matched_rule_id,
                request_id=response.request_id,
            )
            _logger.info(
                "mock_agent_step",
                script=self.name,
                step=index,
                action=result.action,
                disposition=result.disposition,
            )
            results.append(result)
        return results


def _self_test() -> None:
    """Run the happy-path script through a hermetic executor."""
    import tempfile

    from compliance_runtime.config.keys import set_keys_dir

    try:
        with tempfile.TemporaryDirectory() as tmp:
            set_keys_dir(tmp)
            executor = ToolExecutor.from_config(
                "configs/runtime.yaml", db_path=f"{tmp}/a.db"
            )
            agent = MockAgent(
                Path("data/demo/agent_scripts/demo_001.json"), executor
            )
            results = agent.run()
            assert len(results) == 2
            assert all(r.disposition == "allow" for r in results), results
            executor.close()
    finally:
        set_keys_dir(None)
    print("mock_agent.agent self-test: PASS")


if __name__ == "__main__":
    _self_test()
