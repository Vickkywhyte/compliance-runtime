"""Disposition handlers (ADR-006): one pure function per disposition.

Each handler builds a :class:`RuntimeResponse` from the evaluation result and
the recorded evidence. Handlers perform NO I/O and have NO side effects —
persistence happens in the pipeline before dispatch. :func:`dispatch_disposition`
routes to the correct handler.
"""

from __future__ import annotations

from compliance_runtime.dispositions.allow import handle_allow
from compliance_runtime.dispositions.approval import handle_approval
from compliance_runtime.dispositions.deny import handle_deny
from compliance_runtime.dispositions.flagged import handle_flagged
from compliance_runtime.interception.models import RuntimeResponse
from compliance_runtime.policy.models import EvaluationResult
from compliance_runtime.storage.models import ActionRecord, ApprovalRequest, ToolCall

__all__ = [
    "handle_allow",
    "handle_deny",
    "handle_approval",
    "handle_flagged",
    "dispatch_disposition",
]


def dispatch_disposition(
    disposition: str,
    call: ToolCall,
    evaluation: EvaluationResult,
    action_record: ActionRecord,
    policy_version: str,
    approval_request: ApprovalRequest | None = None,
) -> RuntimeResponse:
    """Route an evaluation to its disposition handler. Raises on unknown."""
    if disposition == "allow":
        return handle_allow(call, evaluation, action_record, policy_version)
    if disposition == "deny":
        return handle_deny(call, evaluation, action_record, policy_version)
    if disposition == "require_approval":
        if approval_request is None:
            raise ValueError("require_approval needs an approval_request")
        return handle_approval(
            call, evaluation, action_record, approval_request, policy_version
        )
    if disposition == "allow_with_flag":
        return handle_flagged(call, evaluation, action_record, policy_version)
    raise ValueError(f"unknown disposition: {disposition!r}")
