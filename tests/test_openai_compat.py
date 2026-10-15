"""Tests for the OpenAI-compatible adapter (ADR-002)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from compliance_runtime.interception.models import RuntimeResponse
from compliance_runtime.interception.openai_compat import (
    parse_openai_tool_call,
    to_openai_tool_response,
)

_EXAMPLES = json.loads(
    Path("tests/fixtures/openai_tool_call_examples.json").read_text(encoding="utf-8")
)


def test_parse_valid_tool_call() -> None:
    req = parse_openai_tool_call(_EXAMPLES["valid_single_tool_call"])
    assert req.action == "issue_refund"
    assert req.parameters == {"amount": 250, "currency": "EUR"}
    assert req.agent_id == "support_agent_v3"


def test_parse_missing_tool_calls_raises() -> None:
    with pytest.raises(ValueError):
        parse_openai_tool_call({"agent_id": "a", "session_id": "s"})


def test_parse_empty_tool_calls_raises() -> None:
    with pytest.raises(ValueError):
        parse_openai_tool_call(
            {"tool_calls": [], "agent_id": "a", "session_id": "s"}
        )


def test_parse_malformed_arguments_json_raises() -> None:
    with pytest.raises(ValueError):
        parse_openai_tool_call(_EXAMPLES["malformed_bad_arguments_json"])


def test_parse_missing_function_raises() -> None:
    with pytest.raises(ValueError):
        parse_openai_tool_call(_EXAMPLES["malformed_missing_function"])


def test_parse_multiple_tool_calls_uses_first() -> None:
    req = parse_openai_tool_call(_EXAMPLES["multiple_tool_calls"])
    assert req.parameters == {"amount": 100}  # the first, not 9999


def test_to_openai_tool_response_format() -> None:
    runtime = RuntimeResponse(
        call_id="c", action_id="a", disposition="allow", success=True,
        result={"status": "allowed"}, policy_version="v", reason="ok",
    )
    tool = to_openai_tool_response(runtime, "call_abc123")
    assert tool.role == "tool"
    assert tool.tool_call_id == "call_abc123"
    decoded = json.loads(tool.content)  # content is valid JSON
    assert decoded["disposition"] == "allow"


def test_round_trip() -> None:
    req = parse_openai_tool_call(_EXAMPLES["valid_with_complex_arguments"])
    runtime = RuntimeResponse(
        call_id="c", action_id="a", disposition="require_approval",
        success=None, status="pending", request_id="r", policy_version="v",
        reason="over limit",
    )
    tool = to_openai_tool_response(runtime, "call_def456")
    assert tool.tool_call_id == "call_def456"
    assert json.loads(tool.content)["request_id"] == "r"
    assert req.parameters["meta"]["tags"] == ["vip", "priority"]
