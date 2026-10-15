"""Tests for the approval state machine (C-24)."""

from __future__ import annotations

import pytest

from compliance_runtime.approvals.state import (
    decision_to_state,
    is_terminal,
    validate_transition,
)
from compliance_runtime.exceptions import ApprovalError

_TERMINALS = ("approved", "denied", "modified_approved", "expired")


def test_pending_can_transition_to_approved() -> None:
    validate_transition("pending", "approved")


def test_pending_can_transition_to_denied() -> None:
    validate_transition("pending", "denied")


def test_pending_can_transition_to_modified_approved() -> None:
    validate_transition("pending", "modified_approved")


def test_pending_can_transition_to_expired() -> None:
    validate_transition("pending", "expired")


def test_approved_is_terminal() -> None:
    assert is_terminal("approved")
    with pytest.raises(ApprovalError):
        validate_transition("approved", "denied")


def test_denied_is_terminal() -> None:
    assert is_terminal("denied")
    with pytest.raises(ApprovalError):
        validate_transition("denied", "approved")


def test_modified_approved_is_terminal() -> None:
    assert is_terminal("modified_approved")
    with pytest.raises(ApprovalError):
        validate_transition("modified_approved", "denied")


def test_expired_is_terminal() -> None:
    assert is_terminal("expired")
    with pytest.raises(ApprovalError):
        validate_transition("expired", "approved")


def test_invalid_transition_raises() -> None:
    with pytest.raises(ApprovalError):
        validate_transition("pending", "pending")


def test_decision_to_state_approve() -> None:
    assert decision_to_state("approve") == "approved"


def test_decision_to_state_deny() -> None:
    assert decision_to_state("deny") == "denied"


def test_decision_to_state_modify_approve() -> None:
    assert decision_to_state("modify_approve") == "modified_approved"
