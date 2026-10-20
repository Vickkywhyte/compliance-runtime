"""Thin wrappers for external measurement harnesses (ADR-013).

Exposes three narrow entry points so an external harness can evaluate
policy decisions, append custom entries to the evidence chain, and read
the raw chain bytes — without coupling to internal implementation details.

None of these functions change existing logic; they delegate entirely to
the core modules.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

__all__ = [
    "evaluate_action",
    "append_measurement",
    "read_chain_raw",
]


def evaluate_action(
    action: str,
    parameters: dict[str, Any],
    context: dict[str, Any] | None = None,
    *,
    policy_dir: str | Path = "configs/policies",
    agent_id: str = "harness",
    session_id: str = "harness",
) -> str:
    """Evaluate one action against the loaded policy set and return the disposition.

    Returns one of ``"allow"``, ``"deny"``, ``"require_approval"``, or
    ``"allow_with_flag"``.  No record is written to the evidence chain; this
    is a pure evaluation query (no side effects).

    Args:
        action: The tool/action name to evaluate (e.g. ``"issue_refund"``).
        parameters: The tool-call parameters dict.
        context: Optional entity context dict passed to the policy engine.
        policy_dir: Directory containing the YAML policy files.
        agent_id: Agent identifier used for rate-limit checks.
        session_id: Session identifier carried through the evaluation.
    """
    from compliance_runtime.interception.models import ToolCallRequest
    from compliance_runtime.policy.engine import PolicyEngine
    from compliance_runtime.policy.loader import load_policy_set
    from compliance_runtime.utils.ids import new_ulid, now_utc
    from compliance_runtime.storage.models import ToolCall

    policy_set = load_policy_set(Path(policy_dir))
    engine = PolicyEngine(policy_set)

    # Build a minimal ToolCall so the engine's field resolver has the
    # expected attributes (action, parameters, agent_id, session_id).
    tool_call = ToolCall(
        call_id=new_ulid(),
        correlation_id=new_ulid(),
        agent_id=agent_id,
        session_id=session_id,
        action=action,
        parameters=parameters,
        received_at=now_utc(),
    )
    result = engine.evaluate(tool_call, entity_context=context)
    return result.disposition


def append_measurement(
    db_path: str | Path,
    entry: dict[str, Any],
    *,
    agent_id: str = "harness",
    session_id: str = "harness",
) -> dict[str, Any]:
    """Append a custom measurement entry to the SQLite evidence chain.

    Creates the minimal supporting rows (ToolCall and PolicyEvaluation) that
    the DB schema requires, then delegates to :class:`EvidenceRecorder` so
    the hash chain and signature are maintained exactly as for live actions.

    *entry* must contain ``action`` (str) and ``disposition`` (one of the
    four valid disposition literals).  Any additional keys are stored in
    the ``parameters`` field of the synthetic ToolCall.

    Returns a dict representation of the written :class:`ActionRecord`.
    """
    from compliance_runtime.evidence.recorder import EvidenceRecorder
    from compliance_runtime.policy.models import EvaluationResult
    from compliance_runtime.storage.action_records import ActionRecordRepository
    from compliance_runtime.storage.db import get_connection
    from compliance_runtime.storage.evaluations import EvaluationRepository
    from compliance_runtime.storage.migrate import apply_migrations
    from compliance_runtime.storage.models import PolicyEvaluation, ToolCall
    from compliance_runtime.storage.tool_calls import ToolCallRepository
    from compliance_runtime.utils.ids import new_ulid, now_utc

    if "action" not in entry:
        raise ValueError("entry must include 'action'")
    if "disposition" not in entry:
        raise ValueError("entry must include 'disposition'")

    conn = get_connection(str(db_path))
    apply_migrations(conn)

    # Synthetic ToolCall — parameters carry the measurement payload.
    call = ToolCall(
        call_id=new_ulid(),
        correlation_id=new_ulid(),
        agent_id=agent_id,
        session_id=session_id,
        action=entry["action"],
        parameters={k: v for k, v in entry.items() if k not in ("action", "disposition")},
        received_at=now_utc(),
    )
    ToolCallRepository(conn).insert(call)

    eval_id = new_ulid()
    EvaluationRepository(conn).insert(
        PolicyEvaluation(
            evaluation_id=eval_id,
            call_id=call.call_id,
            matched_rule_id="harness_measurement",
            matched_rule_priority=0,
            policy_version="harness",
            disposition=entry["disposition"],
            reason="external measurement",
            evidence={},
            evaluated_at=now_utc(),
            evaluation_duration_ms=0,
        )
    )

    result = EvaluationResult(
        disposition=entry["disposition"],
        matched_rule_id="harness_measurement",
        matched_rule_priority=0,
        reason="external measurement",
        evidence={},
        policy_version="harness",
        evaluated_at=now_utc(),
        evaluation_duration_ms=0,
    )
    recorder = EvidenceRecorder(ActionRecordRepository(conn))
    record = recorder.record(call, result, evaluation_id=eval_id)
    conn.close()
    return record.model_dump(mode="json")


def read_chain_raw(db_path: str | Path) -> bytes:
    """Return the full action_records chain as raw JSON bytes.

    Rows are returned in chain order (insertion/rowid order) without
    going through Pydantic deserialization, so the bytes reflect exactly
    what is stored in SQLite (useful for offline verification or transport
    to a measurement harness running out-of-process).

    The return value is a UTF-8 JSON array; each element is a row dict with
    string column values exactly as stored.
    """
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM action_records ORDER BY rowid ASC"
        ).fetchall()
        raw: list[dict[str, Any]] = [dict(row) for row in rows]
    finally:
        conn.close()
    return json.dumps(raw, ensure_ascii=False).encode("utf-8")
