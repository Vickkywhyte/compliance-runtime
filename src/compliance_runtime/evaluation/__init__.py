"""Offline evaluation harness (FR-7, ADR-011, 06_EVAL_SPEC.md).

Measures the runtime's three jobs independently — enforcement, evidence, and
oversight — plus operational cost. The harness is deterministic and makes no
LLM or network calls (ADR-013): a benchmark + policy set + fixed seed always
yields the same aggregate metrics.
"""

from __future__ import annotations
