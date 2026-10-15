"""Field-path resolution for policy conditions (05_DATA_SPEC §9).

Pure function, no side effects, no ``eval``/``getattr`` on arbitrary
attributes. Returns ``None`` for any field that cannot be resolved; the
engine treats a ``None`` result as a non-matching condition (never raises
on a missing field — 09_RUNTIME_DESIGN §2.3).
"""

from __future__ import annotations

from typing import Any

from compliance_runtime.storage.models import ToolCall

_RATE_SUFFIX = "_per_minute"


def resolve_field(
    field: str,
    tool_call: ToolCall,
    entity_context: dict[str, Any] | None,
    rate_counters: dict[str, int],
) -> Any | None:
    """Resolve a policy ``field`` path against the call and its context."""
    if field == "action":
        return tool_call.action
    if field == "agent_id":
        return tool_call.agent_id
    if field == "session_id":
        return tool_call.session_id
    if field == "timestamp.hour":
        return tool_call.received_at.hour

    if field.startswith("parameters."):
        name = field.split(".", 1)[1]
        return tool_call.parameters.get(name)

    if field.startswith("entity."):
        if not entity_context:
            return None
        attr = field.split(".", 1)[1]
        return entity_context.get(attr)

    if field.startswith("rate.") and field.endswith(_RATE_SUFFIX):
        action = field[len("rate.") : -len(_RATE_SUFFIX)]
        return rate_counters.get(action, 0)

    return None


def _self_test() -> None:
    """Resolve every supported field pattern plus unknown/missing cases."""
    from datetime import datetime, timezone

    call = ToolCall(
        call_id="c",
        correlation_id="cor",
        agent_id="agent-1",
        session_id="sess-1",
        action="issue_refund",
        parameters={"amount": 750},
        received_at=datetime(2026, 1, 2, 9, 0, tzinfo=timezone.utc),
    )
    assert resolve_field("action", call, None, {}) == "issue_refund"
    assert resolve_field("parameters.amount", call, None, {}) == 750
    assert resolve_field("parameters.missing", call, None, {}) is None
    assert resolve_field("entity.risk", call, {"risk": "high"}, {}) == "high"
    assert resolve_field("entity.risk", call, None, {}) is None
    assert resolve_field("timestamp.hour", call, None, {}) == 9
    assert resolve_field("rate.issue_refund_per_minute", call, None,
                         {"issue_refund": 4}) == 4
    assert resolve_field("unknown.field", call, None, {}) is None
    print("policy.field_resolver self-test: PASS")


if __name__ == "__main__":
    _self_test()
