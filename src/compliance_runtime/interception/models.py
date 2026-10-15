"""Pydantic models for the interception layer (I/O boundary).

``ToolCallRequest`` is the inbound shape; ``RuntimeResponse`` is the typed
result the SDK and HTTP API return; ``OpenAIToolResponse`` wraps it in the
OpenAI tool-message shape (ADR-002).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from compliance_runtime.storage.models import Disposition


class ToolCallRequest(BaseModel):
    """An inbound tool call to evaluate (I/O model: extra keys ignored)."""

    model_config = ConfigDict(extra="ignore")

    action: str
    parameters: dict[str, Any]
    agent_id: str
    session_id: str
    correlation_id: str | None = None
    entity_context: dict[str, Any] | None = None


class RuntimeResponse(BaseModel):
    """The runtime's authorization decision for one tool call."""

    model_config = ConfigDict(extra="forbid")

    call_id: str
    action_id: str
    disposition: Disposition
    success: bool | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    status: str | None = None
    request_id: str | None = None
    expires_at: datetime | None = None
    policy_version: str
    matched_rule_id: str | None = None
    reason: str
    warnings: list[str] = []


class OpenAIToolResponse(BaseModel):
    """An OpenAI-compatible tool message carrying the runtime response JSON."""

    model_config = ConfigDict(extra="forbid")

    tool_call_id: str
    role: Literal["tool"] = "tool"
    content: str  # JSON string of a RuntimeResponse


def _self_test() -> None:
    """Construct each model and confirm defaults."""
    resp = RuntimeResponse(
        call_id="c", action_id="a", disposition="allow", success=True,
        result={"status": "allowed"}, policy_version="v", reason="ok",
    )
    assert resp.warnings == []
    req = ToolCallRequest(
        action="issue_refund", parameters={"amount": 1}, agent_id="a",
        session_id="s",
    )
    assert req.correlation_id is None
    tool = OpenAIToolResponse(tool_call_id="t", content="{}")
    assert tool.role == "tool"
    print("interception.models self-test: PASS")


if __name__ == "__main__":
    _self_test()
