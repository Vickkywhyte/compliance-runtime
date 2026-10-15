"""The :class:`Metric` ABC (06_EVAL_SPEC §3–§6).

The spec's metrics are set-level (precision over all denials, latency p50 over
all requests, …) and read heterogeneous inputs, so a metric computes over an
evaluation *context* rather than a single entry. The context carries:

- ``golden``:   list of ``{"expected_disposition", "expected_rule_id"}``
- ``actual``:   list of ``{"disposition", "matched_rule_id",
  "evidence_complete", "chain_ok", "signature_ok"}`` (aligned with golden)
- ``approvals``: list of ``{"state", "latency_ms"}`` for requests created
- ``timings``:  ``{"runtime_overhead_ms", "policy_eval_ms",
  "evidence_write_ms"}`` → lists of floats
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

Direction = Literal["higher_better", "lower_better"]

EvalContext = dict[str, Any]


class Metric(ABC):
    """A single evaluation metric computed over an :data:`EvalContext`."""

    @abstractmethod
    def compute(self, context: EvalContext) -> float:
        """Return the metric value for the whole evaluation context."""

    @property
    @abstractmethod
    def name(self) -> str:
        """The metric's stable name (matches 06_EVAL_SPEC)."""

    @property
    def direction(self) -> Direction:
        """Whether higher or lower is better (override for FPR/FNR/latency)."""
        return "higher_better"


def _ratio(numerator: int, denominator: int, empty: float) -> float:
    """Safe ratio: returns ``empty`` when the denominator is zero."""
    return numerator / denominator if denominator else empty
