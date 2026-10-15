"""The ``allow_with_flag`` disposition handler (09_RUNTIME_DESIGN §2.4.4)."""

from __future__ import annotations

from compliance_runtime.interception.models import RuntimeResponse
from compliance_runtime.policy.models import EvaluationResult
from compliance_runtime.storage.models import ActionRecord, ToolCall


def handle_flagged(
    call: ToolCall,
    evaluation: EvaluationResult,
    action_record: ActionRecord,
    policy_version: str,
) -> RuntimeResponse:
    """Build the response for an allowed-but-flagged action (review later)."""
    return RuntimeResponse(
        call_id=call.call_id,
        action_id=action_record.action_id,
        disposition="allow_with_flag",
        success=True,
        result={"status": "allowed"},
        policy_version=policy_version,
        matched_rule_id=evaluation.matched_rule_id,
        reason=evaluation.reason,
        warnings=["allowed_with_flag"],
    )
