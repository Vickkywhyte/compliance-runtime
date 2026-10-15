"""Approval state machine (05_DATA_SPEC §2, ADR-007).

``pending`` is the only non-terminal state; every other state is terminal and
rejects further transitions (C-24). The allowed transitions out of ``pending``
mirror the four possible outcomes.
"""

from __future__ import annotations

from compliance_runtime.exceptions import ApprovalError
from compliance_runtime.storage.models import ApprovalDecisionT, ApprovalStateT

VALID_TRANSITIONS: dict[ApprovalStateT, frozenset[ApprovalStateT]] = {
    "pending": frozenset({"approved", "denied", "modified_approved", "expired"}),
    "approved": frozenset(),
    "denied": frozenset(),
    "modified_approved": frozenset(),
    "expired": frozenset(),
}

_DECISION_TO_STATE: dict[ApprovalDecisionT, ApprovalStateT] = {
    "approve": "approved",
    "deny": "denied",
    "modify_approve": "modified_approved",
}


def is_terminal(state: ApprovalStateT) -> bool:
    """Return True if ``state`` permits no further transitions."""
    return len(VALID_TRANSITIONS.get(state, frozenset())) == 0


def validate_transition(current: ApprovalStateT, target: ApprovalStateT) -> None:
    """Raise :class:`ApprovalError` if ``current -> target`` is not allowed."""
    allowed = VALID_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise ApprovalError(
            f"illegal transition {current!r} -> {target!r}"
            + (" (terminal state)" if is_terminal(current) else "")
        )


def decision_to_state(decision: ApprovalDecisionT) -> ApprovalStateT:
    """Map a human decision to its resulting terminal state."""
    try:
        return _DECISION_TO_STATE[decision]
    except KeyError as exc:  # pragma: no cover - guarded by Literal typing
        raise ApprovalError(f"unknown decision: {decision!r}") from exc


def _self_test() -> None:
    """Verify transitions and decision mapping."""
    assert is_terminal("approved") and not is_terminal("pending")
    validate_transition("pending", "approved")  # ok
    for terminal in ("approved", "denied", "modified_approved", "expired"):
        try:
            validate_transition(terminal, "approved")
        except ApprovalError:
            pass
        else:  # pragma: no cover
            raise AssertionError(f"{terminal} should reject transitions")
    assert decision_to_state("approve") == "approved"
    assert decision_to_state("deny") == "denied"
    assert decision_to_state("modify_approve") == "modified_approved"
    print("approvals.state self-test: PASS")


if __name__ == "__main__":
    _self_test()
