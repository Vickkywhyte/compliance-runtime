"""The ``require_approval`` disposition handler (09_RUNTIME_DESIGN §2.4.3)."""

from __future__ import annotations

from compliance_runtime.interception.models import RuntimeResponse
from compliance_runtime.policy.models import EvaluationResult
from compliance_runtime.storage.models import ActionRecord, ApprovalRequest, ToolCall


def handle_approval(
    call: ToolCall,
    evaluation: EvaluationResult,
    action_record: ActionRecord,
    approval_request: ApprovalRequest,
    policy_version: str,
) -> RuntimeResponse:
    """Build the response for a paused action awaiting human approval."""
    return RuntimeResponse(
        call_id=call.call_id,
        action_id=action_record.action_id,
        disposition="require_approval",
        success=None,
        status="pending",
        request_id=approval_request.request_id,
        expires_at=approval_request.expires_at,
        policy_version=policy_version,
        matched_rule_id=evaluation.matched_rule_id,
        reason=evaluation.reason,
    )
