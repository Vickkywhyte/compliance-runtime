"""Tests for the runtime pipeline (FR-1, ADR-013)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from compliance_runtime.config.keys import set_keys_dir
from compliance_runtime.interception.models import ToolCallRequest
from compliance_runtime.interception.pipeline import RuntimePipeline, build_pipeline


@pytest.fixture()
def pipeline(tmp_path: Path) -> Iterator[RuntimePipeline]:
    set_keys_dir(tmp_path)
    pipe, _ = build_pipeline("configs/runtime.yaml", db_path=tmp_path / "t.db")
    try:
        yield pipe
    finally:
        pipe.close()
        set_keys_dir(None)


def _req(amount, entity=None) -> ToolCallRequest:
    return ToolCallRequest(
        action="issue_refund", parameters={"amount": amount, "currency": "EUR"},
        agent_id="a", session_id="s", entity_context=entity,
    )


def test_pipeline_allow_path(pipeline: RuntimePipeline) -> None:
    resp = pipeline.execute(_req(250))
    assert resp.disposition == "allow"
    assert resp.matched_rule_id == "default_allow_refunds"
    assert pipeline.get_action_record(resp.action_id) is not None


def test_pipeline_deny_path(pipeline: RuntimePipeline) -> None:
    resp = pipeline.execute(_req(250, entity={"fraud_flags": ["x"]}))
    assert resp.disposition == "deny"
    assert resp.matched_rule_id == "fraud_flagged_account"


def test_pipeline_approval_path(pipeline: RuntimePipeline) -> None:
    resp = pipeline.execute(_req(850))
    assert resp.disposition == "require_approval"
    assert resp.request_id is not None
    assert pipeline.get_approval(resp.request_id) is not None


def test_pipeline_writes_tool_call(pipeline: RuntimePipeline) -> None:
    resp = pipeline.execute(_req(250))
    records = pipeline.get_evidence_chain_for_call(
        pipeline.get_action_record(resp.action_id).call_id
    )
    assert len(records) == 1


def test_pipeline_writes_policy_evaluation(pipeline: RuntimePipeline) -> None:
    resp = pipeline.execute(_req(250))
    record = pipeline.get_action_record(resp.action_id)
    # The action record references a persisted evaluation (FK enforced).
    assert record.evaluation_id


def test_pipeline_writes_action_record(pipeline: RuntimePipeline) -> None:
    resp = pipeline.execute(_req(250))
    record = pipeline.get_action_record(resp.action_id)
    assert record.previous_hash == "GENESIS"
    assert len(record.current_hash) == 64
    assert record.signature


def test_pipeline_deterministic_disposition(pipeline: RuntimePipeline) -> None:
    a = pipeline.execute(_req(850))
    b = pipeline.execute(_req(850))
    assert a.disposition == b.disposition == "require_approval"
    assert a.matched_rule_id == b.matched_rule_id


def test_pipeline_chain_verifies(pipeline: RuntimePipeline) -> None:
    pipeline.execute(_req(250))
    pipeline.execute(_req(850))
    report = pipeline.verify_chain()
    assert report.chain_integrity and report.signature_validity
    assert report.n_records == 2


def test_pipeline_no_llm_calls() -> None:
    # No module in src/ imports an LLM SDK (ADR-013).
    offenders = []
    for path in Path("src/compliance_runtime").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in ("import openai", "import anthropic", "langchain", "import llama"):
            if needle in text:
                offenders.append((str(path), needle))
    assert offenders == [], offenders
