"""Streamlit compliance dashboard (ADR-012).

Four read-oriented views over the runtime — live actions, approvals, the
evidence chain, and the compliance summary — plus small reusable components.
All ``streamlit`` calls live inside functions so the modules import cleanly
without a running Streamlit server. Approval decisions go only through
``pipeline.decide_approval`` (never the repositories directly); all
DB/parameter text is HTML-escaped before display (C-06).
"""

from __future__ import annotations
