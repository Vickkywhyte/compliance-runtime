"""Oversight metrics (06_EVAL_SPEC §5): approval latency and rates.

Operates on the ``approvals`` context list: ``{"state", "latency_ms"}`` where
``latency_ms`` is ``decided_at - created_at`` in milliseconds (None if the
request was never decided, e.g. it expired).
"""

from __future__ import annotations

from compliance_runtime.evaluation.metrics.base import Direction, EvalContext, Metric, _ratio
from compliance_runtime.evaluation.stats import percentile

_DECIDED = {"approved", "modified_approved", "denied"}


def _latencies(context: EvalContext) -> list[float]:
    return [
        a["latency_ms"]
        for a in context.get("approvals", [])
        if a.get("latency_ms") is not None
    ]


class ApprovalLatencyP50(Metric):
    """Median decision latency in ms. §5.1."""

    @property
    def name(self) -> str:
        return "approval_latency_p50_ms"

    @property
    def direction(self) -> Direction:
        return "lower_better"

    def compute(self, context: EvalContext) -> float:
        latencies = _latencies(context)
        return percentile(latencies, 50) if latencies else 0.0


class ApprovalLatencyP95(Metric):
    """95th-percentile decision latency in ms. §5.1."""

    @property
    def name(self) -> str:
        return "approval_latency_p95_ms"

    @property
    def direction(self) -> Direction:
        return "lower_better"

    def compute(self, context: EvalContext) -> float:
        latencies = _latencies(context)
        return percentile(latencies, 95) if latencies else 0.0


class ApprovalRate(Metric):
    """# (approved OR modified_approved) / # requests. §5.2 (diagnostic)."""

    @property
    def name(self) -> str:
        return "approval_rate"

    def compute(self, context: EvalContext) -> float:
        approvals = context.get("approvals", [])
        approved = sum(
            1 for a in approvals if a["state"] in {"approved", "modified_approved"}
        )
        return _ratio(approved, len(approvals), empty=0.0)


class OverrideRate(Metric):
    """# modified_approved / # (approved OR modified_approved). §5.3."""

    @property
    def name(self) -> str:
        return "override_rate"

    def compute(self, context: EvalContext) -> float:
        approvals = context.get("approvals", [])
        modified = sum(1 for a in approvals if a["state"] == "modified_approved")
        approved = sum(
            1 for a in approvals if a["state"] in {"approved", "modified_approved"}
        )
        return _ratio(modified, approved, empty=0.0)


class AutoDenyRate(Metric):
    """# expired / # requests. §5.4."""

    @property
    def name(self) -> str:
        return "auto_deny_rate"

    @property
    def direction(self) -> Direction:
        return "lower_better"

    def compute(self, context: EvalContext) -> float:
        approvals = context.get("approvals", [])
        expired = sum(1 for a in approvals if a["state"] == "expired")
        return _ratio(expired, len(approvals), empty=0.0)


OVERSIGHT_METRICS = [
    ApprovalLatencyP50(),
    ApprovalLatencyP95(),
    ApprovalRate(),
    OverrideRate(),
    AutoDenyRate(),
]
