"""The approval service: request, decide, expire (ADR-007, C-21 to C-27).

All state changes go through this service (C-21). A decision records the human
choice, transitions the request under an optimistic lock, and writes an audit
event — all in one transaction (C-22, C-23). Terminal states reject further
decisions (C-24); concurrent decisions resolve to exactly one winner (C-25);
expired requests cannot be resurrected (C-26). The service NEVER auto-approves:
the agent proposes, the human decides.
"""

from __future__ import annotations

import sqlite3
from datetime import timedelta
from typing import Any

from compliance_runtime.approvals.state import (
    decision_to_state,
    is_terminal,
    validate_transition,
)
from compliance_runtime.approvals.ttl import (
    expire_if_needed,
    immediate_transaction,
    is_expired,
)
from compliance_runtime.exceptions import (
    ApprovalError,
    ConcurrentModificationError,
    ExpiredApprovalError,
)
from compliance_runtime.policy.models import EvaluationResult
from compliance_runtime.storage.approvals import (
    ApprovalDecisionRepository,
    ApprovalRequestRepository,
)
from compliance_runtime.storage.audit import AuditRepository
from compliance_runtime.storage.models import (
    ApprovalDecision,
    ApprovalDecisionT,
    ApprovalRequest,
    AuditEvent,
    ToolCall,
)
from compliance_runtime.utils.ids import new_ulid, now_utc


class ApprovalService:
    """Single writer for approval state (C-21)."""

    def __init__(
        self,
        request_repo: ApprovalRequestRepository,
        decision_repo: ApprovalDecisionRepository,
        audit_repo: AuditRepository,
        conn: sqlite3.Connection,
    ) -> None:
        self._requests = request_repo
        self._decisions = decision_repo
        self._audit = audit_repo
        self._conn = conn

    # --- creation --------------------------------------------------------

    def request_approval(
        self,
        call: ToolCall,
        evaluation: EvaluationResult,
        action_id: str,
        assignee_role: str,
        severity: str,
        ttl_seconds: int,
    ) -> ApprovalRequest:
        """Create a pending approval request + its audit event (one tx)."""
        created_at = now_utc()
        request = ApprovalRequest(
            request_id=new_ulid(),
            action_id=action_id,
            call_id=call.call_id,
            reason=evaluation.reason,
            matched_rule_id=evaluation.matched_rule_id or "unknown",
            severity=severity,
            assignee_role=assignee_role,
            ttl_seconds=ttl_seconds,
            created_at=created_at,
            expires_at=created_at + timedelta(seconds=ttl_seconds),
            state="pending",
            version=1,
        )
        with immediate_transaction(self._conn):
            self._requests.insert(request, commit=False)
            self._audit.append(
                self._event(
                    "approval_requested",
                    request,
                    {"severity": severity, "assignee_role": assignee_role},
                ),
                commit=False,
            )
        return request

    # --- decision --------------------------------------------------------

    def decide(
        self,
        request_id: str,
        actor_id: str,
        actor_role: str,
        decision: ApprovalDecisionT,
        rationale: str | None = None,
        edits: dict[str, Any] | None = None,
    ) -> ApprovalDecision:
        """Record a human decision on a pending request (C-22, C-23, C-25)."""
        # Read BEFORE taking the write lock so concurrent deciders all capture
        # the same pending version; the optimistic UPDATE is the sole arbiter.
        request = self._requests.get_by_id(request_id)
        if request is None:
            raise ApprovalError(f"approval request not found: {request_id}")

        if is_expired(request) and request.state == "pending":
            expire_if_needed(request, self._requests, self._audit)
            raise ExpiredApprovalError(f"approval request expired: {request_id}")

        if is_terminal(request.state):
            raise ApprovalError(
                f"request {request_id} is in terminal state {request.state!r}"
            )

        target_state = decision_to_state(decision)
        validate_transition(request.state, target_state)

        if decision == "deny" and not (rationale and rationale.strip()):
            raise ApprovalError("deny requires a non-empty rationale")
        if decision == "modify_approve" and not edits:
            raise ApprovalError("modify_approve requires non-empty edits")

        decision_row = ApprovalDecision(
            decision_id=new_ulid(),
            request_id=request_id,
            actor_id=actor_id,
            actor_role=actor_role,
            decision=decision,
            edits=edits,
            rationale=rationale,
            decided_at=now_utc(),
        )

        with immediate_transaction(self._conn):
            self._decisions.insert(decision_row, commit=False)
            won = self._requests.update_state_with_lock(
                request_id, request.version, target_state, commit=False
            )
            if not won:
                # Lost the optimistic lock: another writer already decided.
                raise ConcurrentModificationError(
                    f"request {request_id} was modified concurrently"
                )
            self._audit.append(
                self._event(
                    "approval_decided",
                    request,
                    {"decision": decision, "actor_id": actor_id},
                ),
                commit=False,
            )
        return decision_row

    # --- queries / maintenance ------------------------------------------

    def list_pending(self, role: str | None = None) -> list[ApprovalRequest]:
        """Return pending, non-expired requests (expires stale ones first)."""
        self.expire_stale_requests()
        return self._requests.list_pending(role)

    def expire_stale_requests(self) -> int:
        """Expire every pending, past-TTL request. Idempotent. Returns count."""
        count = 0
        for request in self._requests.list_pending():
            if is_expired(request) and expire_if_needed(
                request, self._requests, self._audit
            ):
                count += 1
        return count

    def audit_chain_for_request(self, request_id: str) -> list[AuditEvent]:
        """Return all audit events for a request, oldest first."""
        return self._audit.query({"entity_id": request_id})

    # --- helpers ---------------------------------------------------------

    @staticmethod
    def _event(
        action: str, request: ApprovalRequest, payload: dict[str, Any]
    ) -> AuditEvent:
        return AuditEvent(
            event_id=new_ulid(),
            occurred_at=now_utc(),
            actor_type="human" if action == "approval_decided" else "system",
            actor_id=payload.get("actor_id", "system"),
            action=action,
            entity_type="approval_request",
            entity_id=request.request_id,
            correlation_id=request.call_id,
            payload=payload,
        )


def _self_test() -> None:
    """Request + approve a flow in-memory and check state + audit chain."""
    from compliance_runtime.storage.action_records import ActionRecordRepository
    from compliance_runtime.storage.db import get_connection
    from compliance_runtime.storage.evaluations import EvaluationRepository
    from compliance_runtime.storage.migrate import apply_migrations
    from compliance_runtime.storage.models import ActionRecord, PolicyEvaluation
    from compliance_runtime.storage.tool_calls import ToolCallRepository

    conn = get_connection(":memory:")
    apply_migrations(conn)
    service = ApprovalService(
        ApprovalRequestRepository(conn),
        ApprovalDecisionRepository(conn),
        AuditRepository(conn),
        conn,
    )
    call = ToolCall(
        call_id=new_ulid(), correlation_id=new_ulid(), agent_id="a",
        session_id="s", action="issue_refund", parameters={"amount": 850},
        received_at=now_utc(),
    )
    evaluation = EvaluationResult(
        disposition="require_approval", matched_rule_id="refund_limit",
        matched_rule_priority=10, reason="over limit", evidence={},
        policy_version="p@1.0.0", evaluated_at=now_utc(),
        evaluation_duration_ms=1,
    )
    # Seed the action_record FK parent.
    eval_id, action_id = new_ulid(), new_ulid()
    ToolCallRepository(conn).insert(call)
    EvaluationRepository(conn).insert(
        PolicyEvaluation(evaluation_id=eval_id, call_id=call.call_id,
                         matched_rule_id="refund_limit", matched_rule_priority=10,
                         policy_version="p@1.0.0", disposition="require_approval",
                         reason="over limit", evidence={}, evaluated_at=now_utc(),
                         evaluation_duration_ms=1)
    )
    ActionRecordRepository(conn).insert(
        ActionRecord(action_id=action_id, call_id=call.call_id, evaluation_id=eval_id,
                     disposition="require_approval", agent_id="a", session_id="s",
                     action="issue_refund", parameters_hash="h", timestamp=now_utc(),
                     previous_hash="GENESIS", current_hash="0" * 64, signature="x",
                     signing_key_id="k", runtime_version="0.1.0")
    )
    request = service.request_approval(
        call, evaluation, action_id=action_id,
        assignee_role="compliance_officer", severity="high", ttl_seconds=900,
    )
    assert request.state == "pending"
    service.decide(request.request_id, "officer", "compliance_officer", "approve")
    updated = ApprovalRequestRepository(conn).get_by_id(request.request_id)
    assert updated.state == "approved" and updated.version == 2
    assert [e.action for e in service.audit_chain_for_request(request.request_id)] == [
        "approval_requested",
        "approval_decided",
    ]
    print("approvals.service self-test: PASS")


if __name__ == "__main__":
    _self_test()
