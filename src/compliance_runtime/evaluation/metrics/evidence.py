"""Evidence metrics (06_EVAL_SPEC §4): completeness, chain integrity, signatures.

Each is the fraction of actions whose per-record boolean flag is True. The
runner populates ``evidence_complete`` (all record fields non-null),
``chain_ok`` (hash recomputes), and ``signature_ok`` (signature verifies) using
the :class:`~compliance_runtime.evidence.verifier.EvidenceVerifier`.
"""

from __future__ import annotations

from compliance_runtime.evaluation.metrics.base import EvalContext, Metric, _ratio


def _fraction_true(context: EvalContext, flag: str) -> float:
    actual = context["actual"]
    hits = sum(1 for a in actual if a.get(flag))
    return _ratio(hits, len(actual), empty=1.0)


class AuditCompleteness(Metric):
    """# with a full ActionRecord / # total. §4.1."""

    @property
    def name(self) -> str:
        return "audit_completeness"

    def compute(self, context: EvalContext) -> float:
        return _fraction_true(context, "evidence_complete")


class ChainIntegrity(Metric):
    """# records whose chain link verifies / # total. §4.2."""

    @property
    def name(self) -> str:
        return "chain_integrity"

    def compute(self, context: EvalContext) -> float:
        return _fraction_true(context, "chain_ok")


class SignatureValidity(Metric):
    """# records whose signature verifies / # total. §4.3."""

    @property
    def name(self) -> str:
        return "signature_validity"

    def compute(self, context: EvalContext) -> float:
        return _fraction_true(context, "signature_ok")


EVIDENCE_METRICS = [AuditCompleteness(), ChainIntegrity(), SignatureValidity()]
