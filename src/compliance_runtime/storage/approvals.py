"""Repositories for approval requests and decisions (05_DATA_SPEC §3.4, §3.5).

``ApprovalRequestRepository`` is read + insert only in Phase 2. The single
locked state transition (``update_state_with_lock``) is added by the Phase 5
``ApprovalService`` and is deliberately NOT present here.

``ApprovalDecisionRepository`` is append-only (decisions are immutable;
``approval_decisions`` has append-only triggers, C-10).
"""

from __future__ import annotations

import json
import sqlite3

from compliance_runtime.exceptions import StorageError
from compliance_runtime.storage.models import ApprovalDecision, ApprovalRequest
from compliance_runtime.utils.ids import canonical_json

_PENDING = "pending"


class ApprovalRequestRepository:
    """Read + insert access to ``approval_requests``."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        # Ensure dict-style row access regardless of how the caller built
        # the connection (not just via storage.db.get_connection).
        self._conn.row_factory = sqlite3.Row

    def insert(self, request: ApprovalRequest) -> None:
        """Insert one approval request. Raises StorageError on conflict."""
        try:
            self._conn.execute(
                """
                INSERT INTO approval_requests (
                    request_id, action_id, call_id, reason, matched_rule_id,
                    severity, assignee_role, ttl_seconds, created_at,
                    expires_at, state, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.request_id,
                    request.action_id,
                    request.call_id,
                    request.reason,
                    request.matched_rule_id,
                    request.severity,
                    request.assignee_role,
                    request.ttl_seconds,
                    request.created_at.isoformat(),
                    request.expires_at.isoformat(),
                    request.state,
                    request.version,
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise StorageError(f"approval_requests insert failed: {exc}") from exc

    def get_by_id(self, request_id: str) -> ApprovalRequest | None:
        """Return the request with ``request_id``, or None if absent."""
        row = self._conn.execute(
            "SELECT * FROM approval_requests WHERE request_id = ?", (request_id,)
        ).fetchone()
        return self._row_to_model(row) if row else None

    def list_pending(self, role: str | None = None) -> list[ApprovalRequest]:
        """Return pending requests, optionally filtered by assignee role."""
        if role is None:
            rows = self._conn.execute(
                "SELECT * FROM approval_requests WHERE state = ? ORDER BY rowid ASC",
                (_PENDING,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM approval_requests "
                "WHERE state = ? AND assignee_role = ? ORDER BY rowid ASC",
                (_PENDING, role),
            ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def count_by_state(self, state: str) -> int:
        """Return the number of requests in a given state."""
        return int(
            self._conn.execute(
                "SELECT COUNT(*) FROM approval_requests WHERE state = ?", (state,)
            ).fetchone()[0]
        )

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> ApprovalRequest:
        return ApprovalRequest.model_validate(dict(row))


class ApprovalDecisionRepository:
    """Append-only access to ``approval_decisions``."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        # Ensure dict-style row access regardless of how the caller built
        # the connection (not just via storage.db.get_connection).
        self._conn.row_factory = sqlite3.Row

    def insert(self, decision: ApprovalDecision) -> None:
        """Insert one approval decision. Raises StorageError on conflict."""
        edits = canonical_json(decision.edits) if decision.edits is not None else None
        try:
            self._conn.execute(
                """
                INSERT INTO approval_decisions (
                    decision_id, request_id, actor_id, actor_role, decision,
                    edits, rationale, decided_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.decision_id,
                    decision.request_id,
                    decision.actor_id,
                    decision.actor_role,
                    decision.decision,
                    edits,
                    decision.rationale,
                    decision.decided_at.isoformat(),
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise StorageError(f"approval_decisions insert failed: {exc}") from exc

    def get_by_request(self, request_id: str) -> list[ApprovalDecision]:
        """Return all decisions for a request, in insertion order."""
        rows = self._conn.execute(
            "SELECT * FROM approval_decisions WHERE request_id = ? ORDER BY rowid ASC",
            (request_id,),
        ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def count(self) -> int:
        """Return the number of stored decisions."""
        return int(
            self._conn.execute(
                "SELECT COUNT(*) FROM approval_decisions"
            ).fetchone()[0]
        )

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> ApprovalDecision:
        data = dict(row)
        data["edits"] = json.loads(data["edits"]) if data["edits"] else None
        return ApprovalDecision.model_validate(data)
