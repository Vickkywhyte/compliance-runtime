"""The end-to-end runtime pipeline (FR-1, ADR-013).

Ties policy evaluation, evidence recording, and the approval workflow together
for one tool call. The same pipeline backs the HTTP server and the Python SDK.
No LLM is ever called; the runtime only authorizes (ADR-013).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from compliance_runtime.approvals.service import ApprovalService
from compliance_runtime.dispositions import dispatch_disposition
from compliance_runtime.evidence.recorder import EvidenceRecorder
from compliance_runtime.evidence.verifier import EvidenceVerifier, VerificationReport
from compliance_runtime.interception.models import RuntimeResponse, ToolCallRequest
from compliance_runtime.policy.engine import PolicyEngine
from compliance_runtime.policy.models import EvaluationResult
from compliance_runtime.storage.action_records import ActionRecordRepository
from compliance_runtime.storage.evaluations import EvaluationRepository
from compliance_runtime.storage.models import (
    ActionRecord,
    ApprovalDecision,
    ApprovalRequest,
    PolicyEvaluation,
    ToolCall,
)
from compliance_runtime.storage.tool_calls import ToolCallRepository
from compliance_runtime.utils.ids import new_ulid, now_utc

_DEFAULT_ROLE = "compliance_officer"
_DEFAULT_SEVERITY = "medium"
_DEFAULT_TTL_SECONDS = 900


class RuntimePipeline:
    """Orchestrates evaluate → record → (approve) → respond for a tool call."""

    def __init__(
        self,
        policy_engine: PolicyEngine,
        evidence_recorder: EvidenceRecorder,
        approval_service: ApprovalService,
        tool_call_repo: ToolCallRepository,
        evaluation_repo: EvaluationRepository,
        action_record_repo: ActionRecordRepository,
        default_ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ) -> None:
        self._engine = policy_engine
        self._recorder = evidence_recorder
        self._approvals = approval_service
        self._tool_calls = tool_call_repo
        self._evaluations = evaluation_repo
        self._action_records = action_record_repo
        self._default_ttl = default_ttl_seconds

    def execute(self, request: ToolCallRequest) -> RuntimeResponse:
        """Run the full pipeline for one tool call and return the response."""
        call = ToolCall(
            call_id=new_ulid(),
            correlation_id=request.correlation_id or new_ulid(),
            agent_id=request.agent_id,
            session_id=request.session_id,
            action=request.action,
            parameters=request.parameters,
            received_at=now_utc(),
            metadata={},
        )
        self._tool_calls.insert(call)

        evaluation = self._engine.evaluate(call, request.entity_context)

        evaluation_id = new_ulid()
        self._evaluations.insert(
            PolicyEvaluation(
                evaluation_id=evaluation_id,
                call_id=call.call_id,
                matched_rule_id=evaluation.matched_rule_id,
                matched_rule_priority=evaluation.matched_rule_priority,
                policy_version=evaluation.policy_version,
                disposition=evaluation.disposition,
                reason=evaluation.reason,
                evidence=evaluation.evidence,
                evaluated_at=evaluation.evaluated_at,
                evaluation_duration_ms=evaluation.evaluation_duration_ms,
            )
        )

        action_record = self._recorder.record(
            call, evaluation, evaluation_id=evaluation_id
        )

        approval_request: ApprovalRequest | None = None
        if evaluation.disposition == "require_approval":
            approval_request = self._create_approval(call, evaluation, action_record)

        return dispatch_disposition(
            evaluation.disposition,
            call,
            evaluation,
            action_record,
            evaluation.policy_version,
            approval_request=approval_request,
        )

    def _create_approval(
        self,
        call: ToolCall,
        evaluation: EvaluationResult,
        action_record: ActionRecord,
    ) -> ApprovalRequest:
        enforcement = evaluation.matched_rule_enforcement
        role = (enforcement.require_role if enforcement else None) or _DEFAULT_ROLE
        severity = (enforcement.severity if enforcement else None) or _DEFAULT_SEVERITY
        ttl = (
            enforcement.ttl_seconds
            if enforcement and enforcement.ttl_seconds is not None
            else self._default_ttl
        )
        return self._approvals.request_approval(
            call, evaluation, action_id=action_record.action_id,
            assignee_role=role, severity=severity, ttl_seconds=ttl,
        )

    # --- approval + evidence convenience entry points --------------------

    def decide_approval(
        self,
        request_id: str,
        actor_id: str,
        actor_role: str,
        decision: str,
        rationale: str | None = None,
        edits: dict[str, Any] | None = None,
    ) -> ApprovalDecision:
        """Record a human decision (delegates to the approval service)."""
        return self._approvals.decide(
            request_id, actor_id, actor_role, decision,
            rationale=rationale, edits=edits,
        )

    def list_pending_approvals(self, role: str | None = None) -> list[ApprovalRequest]:
        """Return pending approval requests, optionally filtered by role."""
        return self._approvals.list_pending(role)

    def get_approval(self, request_id: str) -> ApprovalRequest | None:
        """Return one approval request, or None."""
        return self._approvals._requests.get_by_id(request_id)

    def get_action_record(self, action_id: str) -> ActionRecord | None:
        """Return one action record, or None."""
        return self._action_records.get_by_id(action_id)

    def get_evidence_chain_for_call(self, call_id: str) -> list[ActionRecord]:
        """Return all action records for a given call."""
        return self._action_records.get_by_call(call_id)

    def verify_chain(self) -> VerificationReport:
        """Verify the full evidence chain and signatures."""
        return EvidenceVerifier(self._action_records).verify_all()

    def verify_chain_for(self, action_id: str) -> VerificationReport:
        """Verify one record's hash + signature (used by the evaluator)."""
        return EvidenceVerifier(self._action_records).verify_one(action_id)

    def get_evaluations_for_call(self, call_id: str) -> list[PolicyEvaluation]:
        """Return the persisted policy evaluations for a call."""
        return self._evaluations.get_by_call(call_id)

    def close(self) -> None:
        """Close the underlying DB connection."""
        self._tool_calls._conn.close()


def build_pipeline(
    config_path: str | Path,
    db_path: str | Path | None = None,
    policy_dir: str | Path | None = None,
) -> tuple[RuntimePipeline, sqlite3.Connection]:
    """Wire a RuntimePipeline from config: load policies, open+migrate the DB.

    Returns ``(pipeline, connection)``. The caller owns the connection's
    lifetime (``pipeline.close()`` closes it). Signing keys use whatever
    ``config.keys.set_keys_dir`` is in effect, so callers (and hermetic tests)
    control the key directory.
    """
    from compliance_runtime.config.loader import load_config
    from compliance_runtime.policy.loader import load_policy_set
    from compliance_runtime.storage.approvals import (
        ApprovalDecisionRepository,
        ApprovalRequestRepository,
    )
    from compliance_runtime.storage.audit import AuditRepository
    from compliance_runtime.storage.db import get_connection
    from compliance_runtime.storage.migrate import apply_migrations

    config = load_config(str(config_path))
    policies = Path(policy_dir) if policy_dir else Path(config_path).parent / "policies"
    policy_set = load_policy_set(policies)

    target_db = str(db_path) if db_path is not None else config.runtime.evidence_store_path
    conn = get_connection(target_db)
    apply_migrations(conn)

    engine = PolicyEngine(
        policy_set, default_disposition=config.runtime.default_disposition
    )
    action_repo = ActionRecordRepository(conn)
    approval_service = ApprovalService(
        ApprovalRequestRepository(conn),
        ApprovalDecisionRepository(conn),
        AuditRepository(conn),
        conn,
    )
    pipeline = RuntimePipeline(
        engine,
        EvidenceRecorder(action_repo),
        approval_service,
        ToolCallRepository(conn),
        EvaluationRepository(conn),
        action_repo,
        default_ttl_seconds=config.approvals.default_ttl_seconds,
    )
    return pipeline, conn


def _self_test() -> None:
    """Run one allow path through a hermetic pipeline."""
    import tempfile

    from compliance_runtime.config.keys import set_keys_dir

    try:
        with tempfile.TemporaryDirectory() as tmp:
            set_keys_dir(tmp)
            pipeline, conn = build_pipeline(
                "configs/runtime.yaml", db_path=f"{tmp}/t.db"
            )
            resp = pipeline.execute(
                ToolCallRequest(
                    action="issue_refund", parameters={"amount": 250},
                    agent_id="a", session_id="s",
                )
            )
            assert resp.disposition == "allow", resp.disposition
            assert pipeline.verify_chain().chain_integrity
            pipeline.close()
    finally:
        set_keys_dir(None)
    print("interception.pipeline self-test: PASS")


if __name__ == "__main__":
    _self_test()
