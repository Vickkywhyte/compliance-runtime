"""Repository for the append-only ``action_records`` table (05_DATA_SPEC §3.3).

Append-only is enforced at two layers: SQLite triggers reject UPDATE and
DELETE (C-10, ADR-015), and this repository exposes no mutating methods
(C-11). As defense in depth, :meth:`insert` also validates the hash chain:
a record's ``previous_hash`` must match the last record's ``current_hash``
(or ``"GENESIS"`` for the first record). Full chain verification is a
Phase 4 (evidence) concern; this is a cheap guard at the write boundary.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from compliance_runtime.exceptions import ChainIntegrityError, StorageError
from compliance_runtime.storage.models import ActionRecord

_GENESIS = "GENESIS"
_FORBIDDEN_METHODS = frozenset({"update", "delete", "remove", "modify", "edit"})


class ActionRecordRepository:
    """Append-only access to ``action_records``."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        # Ensure dict-style row access regardless of how the caller built
        # the connection (not just via storage.db.get_connection).
        self._conn.row_factory = sqlite3.Row

    def insert(self, record: ActionRecord) -> None:
        """Insert one signed, hash-chained action record.

        Raises :class:`ChainIntegrityError` if ``previous_hash`` does not
        continue the chain, and :class:`StorageError` on a DB conflict
        (e.g. duplicate ``action_id``, which the triggers also prevent via
        the primary key).
        """
        latest = self.latest()
        expected_previous = latest.current_hash if latest else _GENESIS
        if record.previous_hash != expected_previous:
            raise ChainIntegrityError(
                "previous_hash does not continue the chain: "
                f"expected {expected_previous!r}, got {record.previous_hash!r}"
            )

        try:
            self._conn.execute(
                """
                INSERT INTO action_records (
                    action_id, call_id, evaluation_id, disposition, agent_id,
                    session_id, action, parameters_hash, timestamp,
                    previous_hash, current_hash, signature, signing_key_id,
                    runtime_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.action_id,
                    record.call_id,
                    record.evaluation_id,
                    record.disposition,
                    record.agent_id,
                    record.session_id,
                    record.action,
                    record.parameters_hash,
                    record.timestamp.isoformat(),
                    record.previous_hash,
                    record.current_hash,
                    record.signature,
                    record.signing_key_id,
                    record.runtime_version,
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise StorageError(f"action_records insert failed: {exc}") from exc

    def get_by_id(self, action_id: str) -> ActionRecord | None:
        """Return the record with ``action_id``, or None if absent."""
        row = self._conn.execute(
            "SELECT * FROM action_records WHERE action_id = ?", (action_id,)
        ).fetchone()
        return self._row_to_model(row) if row else None

    def get_by_call(self, call_id: str) -> list[ActionRecord]:
        """Return all records for a call, in insertion order."""
        rows = self._conn.execute(
            "SELECT * FROM action_records WHERE call_id = ? ORDER BY rowid ASC",
            (call_id,),
        ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def latest(self) -> ActionRecord | None:
        """Return the most recently inserted record (for chain building)."""
        row = self._conn.execute(
            "SELECT * FROM action_records ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        return self._row_to_model(row) if row else None

    def count(self) -> int:
        """Return the number of stored action records."""
        return int(
            self._conn.execute("SELECT COUNT(*) FROM action_records").fetchone()[0]
        )

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> ActionRecord:
        return ActionRecord.model_validate(dict(row))

    def __getattr__(self, name: str) -> Any:
        """Reject mutating method names explicitly (C-11)."""
        if name in _FORBIDDEN_METHODS:
            raise AttributeError(
                f"ActionRecordRepository is append-only; '{name}' is not permitted"
            )
        raise AttributeError(name)
