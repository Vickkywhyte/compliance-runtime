"""Mock agent + demo runner (ADR-006, FR-8).

A deterministic, LLM-free agent that replays scripted tool calls through the
runtime, plus an orchestrator that runs the demo scripts and generates a
dossier. Used for the demo and integration tests; never calls an LLM or the
network (ADR-013).
"""

from __future__ import annotations
