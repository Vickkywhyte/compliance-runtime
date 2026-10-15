"""The evaluation runner (06_EVAL_SPEC §10).

Feeds every benchmark entry through the real :class:`RuntimePipeline`, captures
the disposition + evidence outcome, deterministically simulates the human
reviewer for approval requests, then computes all metrics and bootstrap CIs.
No LLM, no network (ADR-013).

The approval *simulator* is an eval stand-in for a human decision: given the
ground truth, it approves when the expected disposition is ``require_approval``
and denies otherwise. It is NOT part of the production runtime.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from compliance_runtime.evaluation.benchmark import (
    BenchmarkEntry,
    load_benchmark,
    validate_benchmark,
)
from compliance_runtime.evaluation.metrics import CI_METRIC_NAMES, all_metrics
from compliance_runtime.evaluation.stats import bootstrap_ci
from compliance_runtime.interception.models import ToolCallRequest
from compliance_runtime.interception.pipeline import RuntimePipeline
from compliance_runtime.policy.models import PolicySet
from compliance_runtime.utils.ids import now_utc

_REQUIRED_RECORD_FIELDS = (
    "action_id", "call_id", "evaluation_id", "disposition", "agent_id",
    "session_id", "action", "parameters_hash", "timestamp", "previous_hash",
    "current_hash", "signature", "signing_key_id", "runtime_version",
)


class EvalReport(BaseModel):
    """Aggregate evaluation report (06_EVAL_SPEC §7)."""

    model_config = ConfigDict(extra="forbid")

    eval_id: str
    run_at: datetime
    benchmark_hash: str
    n_entries: int
    aggregate_metrics: dict[str, float]
    aggregate_ci: dict[str, list[float]]
    per_entry: list[dict[str, Any]]


class EvaluationRunner:
    """Runs a benchmark through the pipeline and computes metrics."""

    def __init__(
        self, pipeline: RuntimePipeline, policy_set: PolicySet, seed: int = 0
    ) -> None:
        self._pipeline = pipeline
        self._policy_set = policy_set
        self._seed = seed

    def run(
        self,
        benchmark_path: Path,
        check_composition: bool = True,
        output_dir: Path | None = None,
    ) -> EvalReport:
        """Evaluate the benchmark and return (and optionally write) the report."""
        entries = load_benchmark(benchmark_path)
        validate_benchmark(entries, self._policy_set, check_composition)
        benchmark_hash = hashlib.sha256(
            Path(benchmark_path).read_bytes()
        ).hexdigest()

        golden: list[dict[str, Any]] = []
        actual: list[dict[str, Any]] = []
        approvals: list[dict[str, Any]] = []
        timings: dict[str, list[float]] = {
            "runtime_overhead_ms": [],
            "policy_eval_ms": [],
            "evidence_write_ms": [],
        }
        per_entry: list[dict[str, Any]] = []

        for entry in entries:
            response, overhead_ms = self._execute(entry)
            record = self._pipeline.get_action_record(response.action_id)

            evidence_complete = self._is_complete(record)
            one = self._pipeline.verify_chain_for(response.action_id)
            chain_ok = one.chain_integrity
            signature_ok = one.signature_validity

            policy_ms = self._policy_eval_ms(record.call_id if record else None)
            timings["runtime_overhead_ms"].append(overhead_ms)
            timings["policy_eval_ms"].append(policy_ms)
            # Evidence-write time is approximated as the non-policy remainder
            # of pipeline latency (dominated by record + persist). Documented
            # proxy — the pipeline does not expose a dedicated timer.
            timings["evidence_write_ms"].append(max(0.0, overhead_ms - policy_ms))

            if response.disposition == "require_approval" and response.request_id:
                approvals.append(
                    self._simulate_decision(response.request_id, entry)
                )

            golden.append(
                {
                    "expected_disposition": entry.expected_disposition,
                    "expected_rule_id": entry.expected_rule_id,
                }
            )
            actual.append(
                {
                    "disposition": response.disposition,
                    "matched_rule_id": response.matched_rule_id,
                    "evidence_complete": evidence_complete,
                    "chain_ok": chain_ok,
                    "signature_ok": signature_ok,
                }
            )
            per_entry.append(
                {
                    "benchmark_id": entry.id,
                    "expected_disposition": entry.expected_disposition,
                    "actual_disposition": response.disposition,
                    "matched_rule_id": response.matched_rule_id,
                    "correct": response.disposition == entry.expected_disposition,
                    "evidence_complete": evidence_complete,
                }
            )

        context = {
            "golden": golden,
            "actual": actual,
            "approvals": approvals,
            "timings": timings,
        }
        aggregate = {m.name: m.compute(context) for m in all_metrics()}
        aggregate_ci = self._compute_ci(actual, approvals)

        report = EvalReport(
            eval_id=f"{now_utc().strftime('%Y%m%dT%H%M%S')}_eval",
            run_at=now_utc(),
            benchmark_hash=benchmark_hash,
            n_entries=len(entries),
            aggregate_metrics=aggregate,
            aggregate_ci=aggregate_ci,
            per_entry=per_entry,
        )
        if output_dir is not None:
            self._write(report, output_dir)
        return report

    # --- per-entry helpers ----------------------------------------------

    def _execute(self, entry: BenchmarkEntry):
        request = ToolCallRequest(
            action=entry.tool_call.action,
            parameters=entry.tool_call.parameters,
            agent_id=entry.tool_call.agent_id,
            session_id=entry.tool_call.session_id,
            entity_context=entry.entity_context,
        )
        start = time.perf_counter()
        response = self._pipeline.execute(request)
        overhead_ms = (time.perf_counter() - start) * 1000.0
        return response, overhead_ms

    @staticmethod
    def _is_complete(record: Any) -> bool:
        if record is None:
            return False
        data = record.model_dump()
        return all(data.get(field) not in (None, "") for field in _REQUIRED_RECORD_FIELDS)

    def _policy_eval_ms(self, call_id: str | None) -> float:
        if call_id is None:
            return 0.0
        evaluations = self._pipeline.get_evaluations_for_call(call_id)
        return float(evaluations[0].evaluation_duration_ms) if evaluations else 0.0

    def _simulate_decision(
        self, request_id: str, entry: BenchmarkEntry
    ) -> dict[str, Any]:
        approve = entry.expected_disposition == "require_approval"
        request = self._pipeline.get_approval(request_id)
        decision = self._pipeline.decide_approval(
            request_id, actor_id="eval_reviewer",
            actor_role="compliance_officer",
            decision="approve" if approve else "deny",
            rationale=None if approve else "eval: expected disposition not approval",
        )
        latency_ms = (decision.decided_at - request.created_at).total_seconds() * 1000.0
        state = "approved" if approve else "denied"
        return {"state": state, "latency_ms": max(0.0, latency_ms)}

    def _compute_ci(
        self,
        actual: list[dict[str, Any]],
        approvals: list[dict[str, Any]],
    ) -> dict[str, list[float]]:
        """Bootstrap CIs for the CI-eligible metrics (06_EVAL_SPEC §8).

        The four per-entry-mean metrics are reported when there are >= 20
        benchmark entries. The three oversight rates are reported over the
        approval requests created during the run, as long as their series is
        non-empty (override_rate requires a non-empty approved/modified set).
        """
        series: dict[str, list[float]] = {}

        if len(actual) >= 20:
            series["policy_coverage"] = [
                1.0 if a["matched_rule_id"] else 0.0 for a in actual
            ]
            series["audit_completeness"] = [
                1.0 if a["evidence_complete"] else 0.0 for a in actual
            ]
            series["chain_integrity"] = [
                1.0 if a["chain_ok"] else 0.0 for a in actual
            ]
            series["signature_validity"] = [
                1.0 if a["signature_ok"] else 0.0 for a in actual
            ]

        approved_set = {"approved", "modified_approved"}
        if approvals:
            series["approval_rate"] = [
                1.0 if a["state"] in approved_set else 0.0 for a in approvals
            ]
            series["auto_deny_rate"] = [
                1.0 if a["state"] == "expired" else 0.0 for a in approvals
            ]
            denominator = [a for a in approvals if a["state"] in approved_set]
            if denominator:  # override_rate is undefined on an empty denominator
                series["override_rate"] = [
                    1.0 if a["state"] == "modified_approved" else 0.0
                    for a in denominator
                ]

        out: dict[str, list[float]] = {}
        for name, values in series.items():
            if name in CI_METRIC_NAMES and values:
                lo, hi = bootstrap_ci(values, seed=self._seed)
                out[name] = [lo, hi]
        return out

    @staticmethod
    def _write(report: EvalReport, output_dir: Path) -> Path:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        path = Path(output_dir) / f"{report.eval_id}.json"
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return path
