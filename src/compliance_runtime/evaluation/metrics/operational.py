"""Operational metrics (06_EVAL_SPEC §6): latency medians and cost.

Reads the ``timings`` context dict. ``cost_per_1k_actions_usd`` is always 0.0
for v1 — the runtime makes no paid API calls (ADR-013).
"""

from __future__ import annotations

from compliance_runtime.evaluation.metrics.base import Direction, EvalContext, Metric
from compliance_runtime.evaluation.stats import percentile


def _p50(context: EvalContext, key: str) -> float:
    series = context.get("timings", {}).get(key, [])
    return percentile(series, 50) if series else 0.0


class RuntimeOverheadP50(Metric):
    """Median added latency per tool call, ms. §6."""

    @property
    def name(self) -> str:
        return "runtime_overhead_p50_ms"

    @property
    def direction(self) -> Direction:
        return "lower_better"

    def compute(self, context: EvalContext) -> float:
        return _p50(context, "runtime_overhead_ms")


class PolicyEvalP50(Metric):
    """Median policy evaluation time, ms. §6."""

    @property
    def name(self) -> str:
        return "policy_eval_p50_ms"

    @property
    def direction(self) -> Direction:
        return "lower_better"

    def compute(self, context: EvalContext) -> float:
        return _p50(context, "policy_eval_ms")


class EvidenceWriteP50(Metric):
    """Median evidence write time, ms. §6."""

    @property
    def name(self) -> str:
        return "evidence_write_p50_ms"

    @property
    def direction(self) -> Direction:
        return "lower_better"

    def compute(self, context: EvalContext) -> float:
        return _p50(context, "evidence_write_ms")


class CostPer1kActionsUsd(Metric):
    """Extrapolated cost per 1k actions — always 0.0 for v1. §6."""

    @property
    def name(self) -> str:
        return "cost_per_1k_actions_usd"

    @property
    def direction(self) -> Direction:
        return "lower_better"

    def compute(self, context: EvalContext) -> float:
        return 0.0


OPERATIONAL_METRICS = [
    RuntimeOverheadP50(),
    PolicyEvalP50(),
    EvidenceWriteP50(),
    CostPer1kActionsUsd(),
]
