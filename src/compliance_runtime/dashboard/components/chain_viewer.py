"""Components for displaying evidence records and verification reports."""

from __future__ import annotations

from typing import Any

import streamlit as st

from compliance_runtime.dashboard.components.approval_form import safe


def trunc(value: str, n: int = 12) -> str:
    """Return the first ``n`` characters of ``value`` (full value if shorter)."""
    return value if len(value) <= n else value[:n]


def render_record(record: Any) -> None:
    """Render one action record's fields, hashes, and signature."""
    st.subheader(f"Action {safe(trunc(record.action_id))}")
    st.write(
        {
            "action_id": safe(record.action_id),
            "call_id": safe(record.call_id),
            "disposition": safe(record.disposition),
            "action": safe(record.action),
            "parameters_hash": safe(record.parameters_hash),
            "previous_hash": safe(record.previous_hash),
            "current_hash": safe(record.current_hash),
            "signing_key_id": safe(record.signing_key_id),
            "runtime_version": safe(record.runtime_version),
        }
    )
    st.caption("Signature (base64)")
    st.code(record.signature, language="text")


def render_verification(report: Any) -> None:
    """Render a verification report with a clear pass/fail indicator."""
    if report.chain_integrity and report.signature_validity:
        st.success(
            f"Chain verified: {report.n_records} records, integrity OK, "
            "signatures OK."
        )
    else:
        st.error(
            f"Verification FAILED at {safe(report.first_broken_at)}: "
            f"{safe(report.broken_reason)}"
        )


def render_chain_table(records: list[Any], page: int, page_size: int) -> None:
    """Render a paginated table of action records (hashes truncated)."""
    start = page * page_size
    window = records[start : start + page_size]
    rows = [
        {
            "action_id": trunc(r.action_id),
            "disposition": r.disposition,
            "timestamp": r.timestamp.isoformat(),
            "previous_hash": trunc(r.previous_hash),
            "current_hash": trunc(r.current_hash),
        }
        for r in window
    ]
    st.dataframe(rows, width="stretch", key="chain_viewer_table")
