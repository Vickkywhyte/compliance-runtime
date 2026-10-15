"""Evidence Chain view: browse records and verify the chain."""

from __future__ import annotations

from typing import Any

import streamlit as st

from compliance_runtime.dashboard.components.chain_viewer import (
    render_chain_table,
    render_record,
    render_verification,
    trunc,
)

_PAGE_SIZE = 50


def render(pipeline: Any) -> None:
    """Render the Evidence Chain tab."""
    st.header("Evidence Chain")
    records = pipeline.all_action_records()

    if st.button("Verify entire chain"):
        render_verification(pipeline.verify_chain())

    if not records:
        st.info("No evidence records yet.")
        return

    page = int(st.number_input("Page", min_value=0, value=0, step=1))
    render_chain_table(records, page, _PAGE_SIZE)

    choice = st.selectbox(
        "Inspect record", ["(none)", *[trunc(r.action_id) for r in records]]
    )
    if choice == "(none)":
        return
    record = next((r for r in records if trunc(r.action_id) == choice), None)
    if record is None:
        return
    render_record(record)
    render_verification(pipeline.verify_chain_for(record.action_id))
