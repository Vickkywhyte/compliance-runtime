"""Streamlit entry point for the compliance dashboard (ADR-012).

Run with: ``streamlit run src/compliance_runtime/dashboard/app.py``.

All Streamlit calls live inside :func:`main`, guarded by the ``__main__``
check, so importing this module (e.g. in ``scripts/doctor.py``) has no side
effects.
"""

from __future__ import annotations

import streamlit as st

from compliance_runtime import __version__
from compliance_runtime.dashboard import state
from compliance_runtime.dashboard.components.policy_info import render_policy_info
from compliance_runtime.dashboard.views import (
    approvals,
    compliance_summary,
    evidence_chain,
    live_actions,
)

_CONFIG_PATH = "configs/runtime.yaml"


def main() -> None:
    """Render the dashboard (invoked by ``streamlit run``)."""
    st.set_page_config(page_title="Compliance Runtime", layout="wide")

    pipeline = state.get_pipeline(_CONFIG_PATH)
    policy_set = pipeline._engine._policy_set  # read-only view of the loaded set

    with st.sidebar:
        st.title("Compliance Runtime")
        st.caption(f"Runtime version {__version__}")
        render_policy_info(policy_set)
        try:
            report = pipeline.verify_chain()
            st.success(f"Evidence OK · {report.n_records} records")
        except Exception:  # noqa: BLE001 - health indicator must not crash the app
            st.warning("Evidence chain unavailable")
        state.set_role(
            st.selectbox("Reviewer role", ["compliance_officer", "ops", "admin"])
        )

    tab_actions, tab_approvals, tab_evidence, tab_summary = st.tabs(
        ["Live Actions", "Approvals", "Evidence Chain", "Compliance Summary"]
    )
    with tab_actions:
        live_actions.render(pipeline)
    with tab_approvals:
        approvals.render(pipeline, state.current_role())
    with tab_evidence:
        evidence_chain.render(pipeline)
    with tab_summary:
        compliance_summary.render(state.results_dir())


if __name__ == "__main__":
    main()
