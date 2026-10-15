"""Approval decision form (ADR-007, C-06).

All decisions go through ``pipeline.decide_approval`` — the dashboard never
touches the approval storage repositories directly. Every DB/user string is
HTML-escaped via :func:`safe` before display (C-06).
"""

from __future__ import annotations

import html
from typing import Any

import streamlit as st

from compliance_runtime.exceptions import ComplianceRuntimeError


def safe(text: Any) -> str:
    """HTML-escape ``text`` for safe display (C-06). Non-strings are coerced."""
    return html.escape(str(text))


def render_approval_actions(pipeline: Any, request_id: str, role: str) -> None:
    """Render Approve / Edit+Approve / Reject controls for one request."""
    col_approve, col_edit, col_reject = st.columns(3)

    with col_approve:
        if st.button("Approve", key=f"approve_{request_id}"):
            _decide(pipeline, request_id, role, "approve", rationale=None)

    with col_edit:
        with st.form(key=f"edit_{request_id}"):
            st.caption("Edit + Approve (metadata only)")
            title = st.text_input("Title", key=f"title_{request_id}")
            description = st.text_area("Description", key=f"desc_{request_id}")
            if st.form_submit_button("Edit + Approve"):
                _decide(
                    pipeline, request_id, role, "modify_approve",
                    edits={"title": title, "description": description},
                )

    with col_reject:
        with st.form(key=f"reject_{request_id}"):
            st.caption("Reject")
            rationale = st.text_area("Reason (required)", key=f"reason_{request_id}")
            if st.form_submit_button("Reject"):
                if not (rationale and rationale.strip()):
                    st.error("A reason is required to reject.")
                else:
                    _decide(pipeline, request_id, role, "deny", rationale=rationale)


def _decide(
    pipeline: Any,
    request_id: str,
    role: str,
    decision: str,
    rationale: str | None = None,
    edits: dict[str, Any] | None = None,
) -> None:
    """Record a decision through the pipeline, surfacing errors cleanly."""
    try:
        pipeline.decide_approval(
            request_id,
            actor_id="dashboard_user",
            actor_role=role,
            decision=decision,
            rationale=rationale,
            edits=edits,
        )
        st.toast(f"Recorded {safe(decision)} for request {safe(request_id[:12])}")
        st.rerun()
    except ComplianceRuntimeError as exc:
        st.error(f"Could not record decision: {safe(exc)}")
