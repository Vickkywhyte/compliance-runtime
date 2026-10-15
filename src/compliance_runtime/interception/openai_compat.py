"""OpenAI-compatible tool-call adapter (ADR-002).

Converts between the OpenAI function-calling shape and the runtime's typed
models. v1 handles one tool call per request (the first).
"""

from __future__ import annotations

import json
from typing import Any

from compliance_runtime.interception.models import (
    OpenAIToolResponse,
    RuntimeResponse,
    ToolCallRequest,
)


def parse_openai_tool_call(openai_payload: dict[str, Any]) -> ToolCallRequest:
    """Parse the first OpenAI tool call into a :class:`ToolCallRequest`.

    Raises :class:`ValueError` on a missing/empty ``tool_calls`` list, a
    malformed function entry, or non-JSON ``arguments``.
    """
    tool_calls = openai_payload.get("tool_calls")
    if not isinstance(tool_calls, list) or not tool_calls:
        raise ValueError("payload must contain a non-empty 'tool_calls' list")

    first = tool_calls[0]
    function = first.get("function") if isinstance(first, dict) else None
    if not isinstance(function, dict) or "name" not in function:
        raise ValueError("first tool call is missing a 'function' with a name")

    raw_args = function.get("arguments", "{}")
    try:
        parameters = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
    except json.JSONDecodeError as exc:
        raise ValueError(f"tool call 'arguments' is not valid JSON: {exc}") from exc
    if not isinstance(parameters, dict):
        raise ValueError("tool call 'arguments' must decode to an object")

    agent_id = openai_payload.get("agent_id")
    session_id = openai_payload.get("session_id")
    if not agent_id or not session_id:
        raise ValueError("payload must include 'agent_id' and 'session_id'")

    return ToolCallRequest(
        action=function["name"],
        parameters=parameters,
        agent_id=agent_id,
        session_id=session_id,
        correlation_id=openai_payload.get("correlation_id"),
        entity_context=openai_payload.get("entity_context"),
    )


def tool_call_id_of(openai_payload: dict[str, Any]) -> str:
    """Return the first tool call's id, or ``""`` if absent."""
    tool_calls = openai_payload.get("tool_calls") or [{}]
    first = tool_calls[0] if isinstance(tool_calls, list) else {}
    return first.get("id", "") if isinstance(first, dict) else ""


def to_openai_tool_response(
    runtime_response: RuntimeResponse, tool_call_id: str
) -> OpenAIToolResponse:
    """Wrap a :class:`RuntimeResponse` as an OpenAI tool message."""
    return OpenAIToolResponse(
        tool_call_id=tool_call_id,
        content=runtime_response.model_dump_json(),
    )


def _self_test() -> None:
    """Round-trip a sample OpenAI payload."""
    payload = {
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "issue_refund",
                    "arguments": '{"amount": 250}',
                },
            }
        ],
        "agent_id": "a",
        "session_id": "s",
    }
    req = parse_openai_tool_call(payload)
    assert req.action == "issue_refund" and req.parameters == {"amount": 250}
    assert tool_call_id_of(payload) == "call_1"
    print("interception.openai_compat self-test: PASS")


if __name__ == "__main__":
    _self_test()
