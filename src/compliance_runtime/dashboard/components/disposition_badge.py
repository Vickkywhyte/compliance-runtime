"""Color-coded badges for dispositions and severities (C-06)."""

from __future__ import annotations

import streamlit as st

from compliance_runtime.dashboard.components.approval_form import safe
from compliance_runtime.dashboard.theme import disposition_color, severity_color

_BADGE = (
    '<span style="background-color:{color};color:white;padding:2px 8px;'
    'border-radius:4px;font-size:0.85em;">{label}</span>'
)


def render_disposition_badge(disposition: str) -> None:
    """Render a colored badge for a disposition (text HTML-escaped)."""
    st.markdown(
        _BADGE.format(color=disposition_color(disposition), label=safe(disposition)),
        unsafe_allow_html=True,
    )


def render_severity_badge(severity: str) -> None:
    """Render a colored badge for a severity level (text HTML-escaped)."""
    st.markdown(
        _BADGE.format(color=severity_color(severity), label=safe(severity)),
        unsafe_allow_html=True,
    )
