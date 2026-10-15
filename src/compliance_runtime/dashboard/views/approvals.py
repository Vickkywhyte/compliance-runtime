"""Approvals view: pending requests and human decisions (ADR-007, C-06).

Decisions are made ONLY via ``pipeline.decide_approval`` (through
``render_approval_actions``); this module never imports or calls the approval
repositories directly.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from compliance_runtime.dashboard.components.approval_form import (
    render_approval_actions,
    safe,
)
from compliance_runtime.dashboard.components.chain_viewer import trunc
from compliance_runtime.dashboard.components.disposition_badge import (
    render_severity_badge,
)


def render(pipeline: Any, role: str) -> None:
    """Render the Approvals tab for reviewer ``role``."""
    st.header("Approvals")
    st.caption(f"Reviewing as role: {safe(role)}")

    pending = pipeline.list_pending_approvals(role)
    if not pending:
        st.info("No pending approvals for your role.")
        return

    rows = [
        {
            "request_id": trunc(r.request_id),
            "call_id": trunc(r.call_id),
            "severity": r.severity,
            "assignee_role": safe(r.assignee_role),
            "created_at": r.created_at.isoformat(),
            "expires_at": r.expires_at.isoformat(),
        }
        for r in pending
    ]
    st.dataframe(rows, use_container_width=True)

    choice = st.selectbox(
        "Decide on request", ["(none)", *[trunc(r.request_id) for r in pending]]
    )
    if choice == "(none)":
        st.caption("Select a request to review.")
        return

    request = next((r for r in pending if trunc(r.request_id) == choice), None)
    if request is None:
        return

    st.subheader(f"Request {safe(trunc(request.request_id))}")
    render_severity_badge(request.severity)
    st.write({
        "reason": safe(request.reason),
        "matched_rule_id": safe(request.matched_rule_id),
        "assignee_role": safe(request.assignee_role),
    })

    call = pipeline.get_tool_call(request.call_id)
    if call is not None:
        st.subheader("Associated tool call")
        st.write({
            "action": safe(call.action),
            "parameters": {k: safe(v) for k, v in call.parameters.items()},
        })

    st.subheader("Decision")
    render_approval_actions(pipeline, request.request_id, role)
