"""Pydantic v2 row models and controlled vocabularies (05_DATA_SPEC §2–§3).

I/O models use ``extra="ignore"`` (ADR-008): callers may attach extra keys
without breaking persistence. Enums are ``Literal`` aliases validated against
the controlled vocabulary in 05_DATA_SPEC §2.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

# --- Controlled vocabularies (05_DATA_SPEC §2) ---------------------------

Disposition = Literal["allow", "deny", "require_approval", "allow_with_flag"]

ApprovalStateT = Literal[
    "pending", "approved", "denied", "modified_approved", "expired"
]

ApprovalDecisionT = Literal["approve", "deny", "modify_approve"]

Operator = Literal[
    "equals",
    "not_equals",
    "greater_than",
    "less_than",
    "greater_or_equal",
    "less_or_equal",
    "in",
    "not_in",
    "matches_regex",
]

ActorType = Literal["agent", "human", "system"]

AuditEntityType = Literal[
    "tool_call",
    "policy_evaluation",
    "action_record",
    "approval_request",
    "approval_decision",
    "audit_event",
]

ErrorCode = Literal[
    "POLICY_DENIED",
    "POLICY_APPROVAL_REQUIRED",
    "POLICY_VALIDATION_FAILED",
    "POLICY_LOAD_FAILED",
    "EVIDENCE_CHAIN_BROKEN",
    "EVIDENCE_SIGNATURE_INVALID",
    "APPROVAL_EXPIRED",
    "APPROVAL_CONFLICT",
    "RUNTIME_INTERNAL_ERROR",
]

Severity = Literal["low", "medium", "high", "critical"]

_IO_CONFIG = ConfigDict(extra="ignore")


# --- Core entities (05_DATA_SPEC §3) -------------------------------------


class ToolCall(BaseModel):
    """A single intercepted tool call (05_DATA_SPEC §3.1)."""

    model_config = _IO_CONFIG

    call_id: str
    correlation_id: str
    agent_id: str
    session_id: str
    action: str
    parameters: dict[str, Any]
    received_at: datetime
    metadata: dict[str, Any] = {}


class PolicyEvaluation(BaseModel):
    """The result of evaluating a tool call against the policy set (§3.2)."""

    model_config = _IO_CONFIG

    evaluation_id: str
    call_id: str
    matched_rule_id: str | None
    matched_rule_priority: int | None
    policy_version: str
    disposition: Disposition
    reason: str
    evidence: dict[str, Any]
    evaluated_at: datetime
    evaluation_duration_ms: int


class ActionRecord(BaseModel):
    """A signed, hash-chained record of an authorized action (§3.3)."""

    model_config = _IO_CONFIG

    action_id: str
    call_id: str
    evaluation_id: str
    disposition: Disposition
    agent_id: str
    session_id: str
    action: str
    parameters_hash: str
    timestamp: datetime

    previous_hash: str
    current_hash: str
    signature: str
    signing_key_id: str

    runtime_version: str


class ApprovalRequest(BaseModel):
    """A pending human-approval request (§3.4)."""

    model_config = _IO_CONFIG

    request_id: str
    action_id: str
    call_id: str
    reason: str
    matched_rule_id: str
    severity: Severity
    assignee_role: str
    ttl_seconds: int
    created_at: datetime
    expires_at: datetime
    state: ApprovalStateT
    version: int


class ApprovalDecision(BaseModel):
    """A human decision on an approval request (§3.5)."""

    model_config = _IO_CONFIG

    decision_id: str
    request_id: str
    actor_id: str
    actor_role: str
    decision: ApprovalDecisionT
    edits: dict[str, Any] | None = None
    rationale: str | None = None
    decided_at: datetime


class AuditEvent(BaseModel):
    """An append-only audit-trail event (§3.6)."""

    model_config = _IO_CONFIG

    event_id: str
    occurred_at: datetime
    actor_type: ActorType
    actor_id: str
    action: str
    entity_type: AuditEntityType
    entity_id: str
    correlation_id: str
    payload: dict[str, Any]


def _self_test() -> None:
    """Construct each model from representative data."""
    from compliance_runtime.utils.ids import new_ulid, now_utc

    now = now_utc()
    call = ToolCall(
        call_id=new_ulid(),
        correlation_id=new_ulid(),
        agent_id="agent-1",
        session_id="sess-1",
        action="issue_refund",
        parameters={"amount": 42},
        received_at=now,
    )
    assert call.metadata == {}

    event = AuditEvent(
        event_id=new_ulid(),
        occurred_at=now,
        actor_type="system",
        actor_id="system",
        action="action_recorded",
        entity_type="action_record",
        entity_id=new_ulid(),
        correlation_id=call.correlation_id,
        payload={"ok": True},
    )
    assert event.entity_type == "action_record"

    # extra="ignore": unknown keys are dropped, not rejected.
    loose = ToolCall.model_validate(
        {**call.model_dump(), "unknown_extra": "dropped"}
    )
    assert not hasattr(loose, "unknown_extra")

    print("storage.models self-test: PASS")


if __name__ == "__main__":
    _self_test()
