"""Tests for the policy field resolver (05_DATA_SPEC §9)."""

from __future__ import annotations

from datetime import datetime, timezone

from compliance_runtime.policy.field_resolver import resolve_field
from compliance_runtime.storage.models import ToolCall


def _call(**overrides: object) -> ToolCall:
    base = {
        "call_id": "c",
        "correlation_id": "cor",
        "agent_id": "agent-1",
        "session_id": "sess-1",
        "action": "issue_refund",
        "parameters": {"amount": 750, "currency": "EUR"},
        "received_at": datetime(2026, 1, 2, 14, 0, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return ToolCall(**base)


def test_resolve_action() -> None:
    assert resolve_field("action", _call(), None, {}) == "issue_refund"


def test_resolve_simple_parameter() -> None:
    assert resolve_field("parameters.amount", _call(), None, {}) == 750


def test_resolve_nested_parameter() -> None:
    # v1 supports single-level parameter paths; a deeper path is unknown.
    call = _call(parameters={"data": {"amount": 99}})
    assert resolve_field("parameters.data.amount", call, None, {}) is None


def test_resolve_missing_parameter_returns_none() -> None:
    assert resolve_field("parameters.missing", _call(), None, {}) is None


def test_resolve_entity_attribute() -> None:
    assert resolve_field("entity.risk", _call(), {"risk": "high"}, {}) == "high"


def test_resolve_missing_entity_context_returns_none() -> None:
    assert resolve_field("entity.risk", _call(), None, {}) is None


def test_resolve_timestamp_hour() -> None:
    assert resolve_field("timestamp.hour", _call(), None, {}) == 14


def test_resolve_rate_counter() -> None:
    assert resolve_field(
        "rate.issue_refund_per_minute", _call(), None, {"issue_refund": 7}
    ) == 7


def test_resolve_unknown_field_returns_none() -> None:
    assert resolve_field("totally.unknown", _call(), None, {}) is None
