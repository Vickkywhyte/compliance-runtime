"""AI Compliance Runtime.

An open-source runtime that intercepts AI agent tool calls, enforces policy
in real time, requires human approval for high-stakes actions, and produces
cryptographically-verifiable evidence for regulators.

See ``claude_chat/`` for the full design docs. This package is built one
phase at a time per ``claude_chat/08_ROADMAP.md``.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
