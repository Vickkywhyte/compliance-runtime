"""The ``deny`` disposition handler (ADR-006, 09_RUNTIME_DESIGN §2.4.2)."""

from __future__ import annotations

from compliance_runtime.interception.models import RuntimeResponse
from compliance_runtime.policy.models import EvaluationResult
from compliance_runtime.storage.models import ActionRecord, ToolCall


def handle_deny(
    call: ToolCall,
    evaluation: EvaluationResult,
    action_record: ActionRecord,
    policy_version: str,
) -> RuntimeResponse:
    """Build the response for a denied action (caller MUST NOT execute)."""
    return RuntimeResponse(
        call_id=call.call_id,
        action_id=action_record.action_id,
        disposition="deny",
        success=False,
        error={
            "code": "POLICY_DENIED",
            "message": evaluation.reason,
            "rule_id": evaluation.matched_rule_id,
            "evidence": evaluation.evidence,
        },
        policy_version=policy_version,
        matched_rule_id=evaluation.matched_rule_id,
        reason=evaluation.reason,
    )
