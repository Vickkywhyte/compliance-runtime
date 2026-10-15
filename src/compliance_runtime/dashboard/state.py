"""Session-state helpers and the cached pipeline builder.

The pipeline is built once per session via ``@st.cache_resource`` (decorating
at import is side-effect-free; the wrapped function only runs when called
inside a Streamlit session).
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from compliance_runtime.interception.pipeline import RuntimePipeline, build_pipeline

_DEFAULT_ROLE = "compliance_officer"

# Session-state keys shared across tabs.
PIPELINE = "pipeline"
CURRENT_ROLE = "current_role"
SELECTED_ACTION_ID = "selected_action_id"
SELECTED_REQUEST_ID = "selected_request_id"
SELECTED_RUN_ID = "selected_run_id"


@st.cache_resource
def get_pipeline(config_path: str, db_path: str | None = None) -> RuntimePipeline:
    """Build (once) and return the runtime pipeline for the dashboard."""
    pipeline, _ = build_pipeline(config_path, db_path=db_path)
    return pipeline


def current_role() -> str:
    """Return the reviewer role in session (defaults to compliance_officer)."""
    return st.session_state.get(CURRENT_ROLE, _DEFAULT_ROLE)


def set_role(role: str) -> None:
    st.session_state[CURRENT_ROLE] = role


def get_selected(key: str) -> str | None:
    """Return a selected id from session state, or None."""
    return st.session_state.get(key)


def set_selected(key: str, value: str | None) -> None:
    st.session_state[key] = value


def results_dir() -> Path:
    """Directory holding eval reports."""
    return Path("results/evals")
