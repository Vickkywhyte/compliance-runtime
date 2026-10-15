"""In-process Python SDK (ADR-011).

``ToolExecutor`` runs the same :class:`RuntimePipeline` as the HTTP server,
synchronously, for agents written in Python. Keys use whatever
``config.keys.set_keys_dir`` is in effect (default ~/.compliance-runtime/keys).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from compliance_runtime.interception.models import (
    OpenAIToolResponse,
    RuntimeResponse,
    ToolCallRequest,
)
from compliance_runtime.interception.openai_compat import (
    parse_openai_tool_call,
    to_openai_tool_response,
    tool_call_id_of,
)
from compliance_runtime.interception.pipeline import RuntimePipeline, build_pipeline


class ToolExecutor:
    """Synchronous, in-process entry point to the runtime pipeline."""

    def __init__(self, pipeline: RuntimePipeline) -> None:
        self._pipeline = pipeline

    @classmethod
    def from_config(
        cls,
        config_path: str | Path,
        db_path: str | Path | None = None,
    ) -> ToolExecutor:
        """Load policies, open + migrate the DB, and wire the pipeline."""
        pipeline, _ = build_pipeline(config_path, db_path=db_path)
        return cls(pipeline)

    def execute(
        self,
        action: str,
        parameters: dict[str, Any],
        agent_id: str,
        session_id: str,
        entity_context: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> RuntimeResponse:
        """Run the pipeline synchronously and return the typed response."""
        return self._pipeline.execute(
            ToolCallRequest(
                action=action,
                parameters=parameters,
                agent_id=agent_id,
                session_id=session_id,
                entity_context=entity_context,
                correlation_id=correlation_id,
            )
        )

    def execute_openai_tool_call(self, payload: dict[str, Any]) -> OpenAIToolResponse:
        """Accept an OpenAI tool call payload; return an OpenAI tool response."""
        request = parse_openai_tool_call(payload)
        response = self._pipeline.execute(request)
        return to_openai_tool_response(response, tool_call_id_of(payload))

    @property
    def pipeline(self) -> RuntimePipeline:
        """The underlying pipeline (for approval/evidence operations)."""
        return self._pipeline

    def close(self) -> None:
        """Close the DB connection."""
        self._pipeline.close()

    def __enter__(self) -> ToolExecutor:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def _self_test() -> None:
    """Execute one allow call through the SDK in a temp DB + key dir."""
    import tempfile

    from compliance_runtime.config.keys import set_keys_dir

    try:
        with tempfile.TemporaryDirectory() as tmp:
            set_keys_dir(tmp)
            with ToolExecutor.from_config(
                "configs/runtime.yaml", db_path=f"{tmp}/t.db"
            ) as ex:
                resp = ex.execute(
                    "issue_refund", {"amount": 250}, agent_id="a", session_id="s"
                )
                assert resp.disposition == "allow", resp.disposition
    finally:
        set_keys_dir(None)
    print("interception.sdk self-test: PASS")


if __name__ == "__main__":
    _self_test()
