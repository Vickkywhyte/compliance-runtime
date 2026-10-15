"""Repository for the ``tool_calls`` table (05_DATA_SPEC §3.1).

Insert + read access only. Tool calls are append-only by convention in v1
(application code never updates them); trigger-level enforcement is a v2
concern. All SQL is parameterized.
"""

from __future__ import annotations

import json
import sqlite3

from compliance_runtime.exceptions import StorageError
from compliance_runtime.storage.models import ToolCall
from compliance_runtime.utils.ids import canonical_json


class ToolCallRepository:
    """Append-by-convention access to ``tool_calls``."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        # Ensure dict-style row access regardless of how the caller built
        # the connection (not just via storage.db.get_connection).
        self._conn.row_factory = sqlite3.Row

    def insert(self, call: ToolCall) -> None:
        """Insert one tool call, serializing JSON fields. Raises StorageError."""
        try:
            self._conn.execute(
                """
                INSERT INTO tool_calls (
                    call_id, correlation_id, agent_id, session_id, action,
                    parameters, received_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    call.call_id,
                    call.correlation_id,
                    call.agent_id,
                    call.session_id,
                    call.action,
                    canonical_json(call.parameters),
                    call.received_at.isoformat(),
                    canonical_json(call.metadata),
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise StorageError(f"tool_calls insert failed: {exc}") from exc

    def get_by_id(self, call_id: str) -> ToolCall | None:
        """Return the tool call with ``call_id``, or None if absent."""
        row = self._conn.execute(
            "SELECT * FROM tool_calls WHERE call_id = ?", (call_id,)
        ).fetchone()
        return self._row_to_model(row) if row else None

    def get_by_correlation(self, correlation_id: str) -> list[ToolCall]:
        """Return all tool calls in a correlation group, in insertion order."""
        rows = self._conn.execute(
            "SELECT * FROM tool_calls WHERE correlation_id = ? ORDER BY rowid ASC",
            (correlation_id,),
        ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def count(self) -> int:
        """Return the number of stored tool calls."""
        return int(self._conn.execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0])

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> ToolCall:
        data = dict(row)
        data["parameters"] = json.loads(data["parameters"])
        data["metadata"] = json.loads(data["metadata"]) if data["metadata"] else {}
        return ToolCall.model_validate(data)
