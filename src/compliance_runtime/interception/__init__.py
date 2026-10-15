"""Interception layer: pipeline, HTTP server, Python SDK, OpenAI adapter.

The runtime intercepts OpenAI-compatible tool calls (ADR-002), runs the
policy → evidence → approval pipeline, and returns a typed response. The same
pipeline backs both the HTTP server (ADR-010) and the in-process Python SDK
(ADR-011). No LLM is ever called (ADR-013); the runtime only authorizes.
"""

from __future__ import annotations
