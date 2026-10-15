"""Repository for the ``policy_evaluations`` table (05_DATA_SPEC §3.2).

Insert + read access only; no update/delete. All SQL is parameterized.
"""

from __future__ import annotations

import json
import sqlite3

from compliance_runtime.exceptions import StorageError
from compliance_runtime.storage.models import PolicyEvaluation
from compliance_runtime.utils.ids import canonical_json


class EvaluationRepository:
    """Access to ``policy_evaluations``."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        # Ensure dict-style row access regardless of how the caller built
        # the connection (not just via storage.db.get_connection).
        self._conn.row_factory = sqlite3.Row

    def insert(self, evaluation: PolicyEvaluation) -> None:
        """Insert one policy evaluation. Raises StorageError on conflict."""
        try:
            self._conn.execute(
                """
                INSERT INTO policy_evaluations (
                    evaluation_id, call_id, matched_rule_id,
                    matched_rule_priority, policy_version, disposition,
                    reason, evidence, evaluated_at, evaluation_duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evaluation.evaluation_id,
                    evaluation.call_id,
                    evaluation.matched_rule_id,
                    evaluation.matched_rule_priority,
                    evaluation.policy_version,
                    evaluation.disposition,
                    evaluation.reason,
                    canonical_json(evaluation.evidence),
                    evaluation.evaluated_at.isoformat(),
                    evaluation.evaluation_duration_ms,
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise StorageError(f"policy_evaluations insert failed: {exc}") from exc

    def get_by_id(self, evaluation_id: str) -> PolicyEvaluation | None:
        """Return the evaluation with ``evaluation_id``, or None if absent."""
        row = self._conn.execute(
            "SELECT * FROM policy_evaluations WHERE evaluation_id = ?",
            (evaluation_id,),
        ).fetchone()
        return self._row_to_model(row) if row else None

    def get_by_call(self, call_id: str) -> list[PolicyEvaluation]:
        """Return all evaluations for a call (one per call in v1)."""
        rows = self._conn.execute(
            "SELECT * FROM policy_evaluations WHERE call_id = ? ORDER BY rowid ASC",
            (call_id,),
        ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def count(self) -> int:
        """Return the number of stored evaluations."""
        return int(
            self._conn.execute(
                "SELECT COUNT(*) FROM policy_evaluations"
            ).fetchone()[0]
        )

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> PolicyEvaluation:
        data = dict(row)
        data["evidence"] = json.loads(data["evidence"])
        return PolicyEvaluation.model_validate(data)
