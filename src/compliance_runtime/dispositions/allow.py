"""The ``allow`` disposition handler (ADR-006, 09_RUNTIME_DESIGN §2.4.1)."""

from __future__ import annotations

from compliance_runtime.interception.models import RuntimeResponse
from compliance_runtime.policy.models import EvaluationResult
from compliance_runtime.storage.models import ActionRecord, ToolCall


def handle_allow(
    call: ToolCall,
    evaluation: EvaluationResult,
    action_record: ActionRecord,
    policy_version: str,
) -> RuntimeResponse:
    """Build the response for an allowed action (caller executes the tool)."""
    return RuntimeResponse(
        call_id=call.call_id,
        action_id=action_record.action_id,
        disposition="allow",
        success=True,
        result={"status": "allowed"},
        policy_version=policy_version,
        matched_rule_id=evaluation.matched_rule_id,
        reason=evaluation.reason,
    )
