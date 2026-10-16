"""Live Actions view: recent tool calls and their dispositions (C-06)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from compliance_runtime.dashboard.components.approval_form import safe
from compliance_runtime.dashboard.components.disposition_badge import (
    render_disposition_badge,
)
from compliance_runtime.dashboard.components.chain_viewer import trunc

_PAGE_SIZE = 50


def render(pipeline: Any) -> None:
    """Render the Live Actions tab."""
    st.header("Live Actions")
    records = list(reversed(pipeline.all_action_records()))  # newest first

    if not records:
        st.info("No actions yet. Run `make demo` or execute a tool call.")
        return

    actions = sorted({r.action for r in records})
    dispositions = sorted({r.disposition for r in records})
    col_a, col_d = st.columns(2)
    action_filter = col_a.selectbox(
        "Action", ["(all)", *actions], key="live_actions_action_filter"
    )
    disp_filter = col_d.selectbox(
        "Disposition", ["(all)", *dispositions], key="live_actions_disposition_filter"
    )

    filtered = [
        r for r in records
        if (action_filter in ("(all)", r.action))
        and (disp_filter in ("(all)", r.disposition))
    ]

    page = int(st.number_input(
        "Page", min_value=0, value=0, step=1, key="live_actions_page"
    ))
    window = filtered[page * _PAGE_SIZE : (page + 1) * _PAGE_SIZE]

    table, detail = st.columns([2, 1])
    with table:
        rows = [
            {
                "call_id": trunc(r.call_id),
                "action": safe(r.action),
                "agent_id": safe(r.agent_id),
                "disposition": r.disposition,
                "matched_rule": safe(_rule_for(pipeline, r)),
                "timestamp": r.timestamp.isoformat(),
            }
            for r in window
        ]
        st.dataframe(rows, width="stretch", key="live_actions_table")
        selected = st.selectbox(
            "Inspect action", ["(none)", *[trunc(r.action_id) for r in window]],
            key="live_actions_inspect",
        )

    with detail:
        _render_detail(pipeline, window, selected)


def _rule_for(pipeline: Any, record: Any) -> str:
    evaluations = pipeline.get_evaluations_for_call(record.call_id)
    if evaluations and evaluations[0].matched_rule_id:
        return evaluations[0].matched_rule_id
    return "—"


def _render_detail(pipeline: Any, window: list[Any], selected: str) -> None:
    if selected == "(none)":
        st.caption("Select an action to inspect.")
        return
    record = next((r for r in window if trunc(r.action_id) == selected), None)
    if record is None:
        return
    st.subheader("Disposition")
    render_disposition_badge(record.disposition)

    call = pipeline.get_tool_call(record.call_id)
    if call is not None:
        st.subheader("Tool call")
        st.write({
            "action": safe(call.action),
            "agent_id": safe(call.agent_id),
            "parameters": {k: safe(v) for k, v in call.parameters.items()},
        })

    evaluations = pipeline.get_evaluations_for_call(record.call_id)
    if evaluations:
        ev = evaluations[0]
        st.subheader("Policy evaluation")
        st.write({
            "disposition": safe(ev.disposition),
            "matched_rule_id": safe(ev.matched_rule_id),
            "reason": safe(ev.reason),
        })

    st.subheader("Action record")
    st.write({
        "action_id": safe(record.action_id),
        "current_hash": safe(record.current_hash),
        "signing_key_id": safe(record.signing_key_id),
    })
    st.caption("See the Evidence Chain tab for full verification.")
