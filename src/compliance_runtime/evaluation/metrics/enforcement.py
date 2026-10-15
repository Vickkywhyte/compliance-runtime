"""Enforcement metrics (06_EVAL_SPEC §3): precision, recall, FPR, FNR, coverage.

"Denied" means the actual disposition is ``deny``; "expected denied" means the
golden disposition is ``deny``. Everything else counts as permitted.
"""

from __future__ import annotations

from compliance_runtime.evaluation.metrics.base import Direction, EvalContext, Metric, _ratio

_DENY = "deny"


def _pairs(context: EvalContext):
    return list(zip(context["golden"], context["actual"]))


class PolicyPrecision(Metric):
    """# (denied AND expected denied) / # denied. §3.1."""

    @property
    def name(self) -> str:
        return "policy_precision"

    def compute(self, context: EvalContext) -> float:
        tp = fp = 0
        for golden, actual in _pairs(context):
            if actual["disposition"] == _DENY:
                if golden["expected_disposition"] == _DENY:
                    tp += 1
                else:
                    fp += 1
        return _ratio(tp, tp + fp, empty=1.0)


class PolicyRecall(Metric):
    """# (denied AND expected denied) / # expected denied. §3.2."""

    @property
    def name(self) -> str:
        return "policy_recall"

    def compute(self, context: EvalContext) -> float:
        tp = fn = 0
        for golden, actual in _pairs(context):
            if golden["expected_disposition"] == _DENY:
                if actual["disposition"] == _DENY:
                    tp += 1
                else:
                    fn += 1
        return _ratio(tp, tp + fn, empty=1.0)


class FalsePositiveRate(Metric):
    """# (denied BUT expected allowed) / # expected allowed. §3.3."""

    @property
    def name(self) -> str:
        return "false_positive_rate"

    @property
    def direction(self) -> Direction:
        return "lower_better"

    def compute(self, context: EvalContext) -> float:
        fp = expected_allowed = 0
        for golden, actual in _pairs(context):
            if golden["expected_disposition"] != _DENY:
                expected_allowed += 1
                if actual["disposition"] == _DENY:
                    fp += 1
        return _ratio(fp, expected_allowed, empty=0.0)


class FalseNegativeRate(Metric):
    """# (allowed BUT expected denied) / # expected denied. §3.4."""

    @property
    def name(self) -> str:
        return "false_negative_rate"

    @property
    def direction(self) -> Direction:
        return "lower_better"

    def compute(self, context: EvalContext) -> float:
        fn = expected_denied = 0
        for golden, actual in _pairs(context):
            if golden["expected_disposition"] == _DENY:
                expected_denied += 1
                if actual["disposition"] != _DENY:
                    fn += 1
        return _ratio(fn, expected_denied, empty=0.0)


class PolicyCoverage(Metric):
    """# with a matched rule / # total. §3.5."""

    @property
    def name(self) -> str:
        return "policy_coverage"

    def compute(self, context: EvalContext) -> float:
        actual = context["actual"]
        covered = sum(1 for a in actual if a.get("matched_rule_id") is not None)
        return _ratio(covered, len(actual), empty=1.0)


ENFORCEMENT_METRICS = [
    PolicyPrecision(),
    PolicyRecall(),
    FalsePositiveRate(),
    FalseNegativeRate(),
    PolicyCoverage(),
]
