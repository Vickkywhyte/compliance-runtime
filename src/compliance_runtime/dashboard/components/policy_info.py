"""Component showing the loaded policy set's identity (C-30)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from compliance_runtime.dashboard.components.approval_form import safe


def render_policy_info(policy_set: Any) -> None:
    """Show policy name/version, content hash (C-30), and rule counts."""
    n_rules = sum(len(p.rules) for p in policy_set.policies)
    names = ", ".join(safe(p.name) for p in policy_set.policies)
    st.markdown(f"**Policies:** {names}")
    st.markdown(f"**Version:** {safe(policy_set.version)}")
    st.markdown(f"**Policies loaded:** {len(policy_set.policies)}  ·  "
                f"**Rules:** {n_rules}")
    st.caption("Policy content hash (C-30)")
    st.code(policy_set.content_hash, language="text")
