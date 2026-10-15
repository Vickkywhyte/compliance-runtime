"""Append-only audit repository (C-11, C-23).

The repository exposes ``append`` and ``query`` only. There is deliberately
no ``update`` or ``delete`` method: mutation of ``audit_events`` is forbidden
at the API layer (C-11) and also rejected by SQLite triggers (C-10). Any
attempt to call a mutating method raises :class:`AttributeError` via
:meth:`__getattr__`.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from compliance_runtime.storage.models import AuditEvent
from compliance_runtime.utils.ids import canonical_json

_FORBIDDEN_METHODS = frozenset({"update", "delete", "remove", "modify", "edit"})

_QUERYABLE_FIELDS = frozenset(
    {
        "event_id",
        "actor_type",
        "actor_id",
        "action",
        "entity_type",
        "entity_id",
        "correlation_id",
    }
)


class AuditRepository:
    """Append-only access to the ``audit_events`` table."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        # Ensure dict-style row access regardless of how the caller built
        # the connection (not just via storage.db.get_connection).
        self._conn.row_factory = sqlite3.Row

    def append(self, event: AuditEvent) -> None:
        """Insert one audit event. No update path exists by design."""
        self._conn.execute(
            """
            INSERT INTO audit_events (
                event_id, occurred_at, actor_type, actor_id, action,
                entity_type, entity_id, correlation_id, payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.occurred_at.isoformat(),
                event.actor_type,
                event.actor_id,
                event.action,
                event.entity_type,
                event.entity_id,
                event.correlation_id,
                canonical_json(event.payload),
            ),
        )
        self._conn.commit()

    def query(self, filters: dict[str, Any] | None = None) -> list[AuditEvent]:
        """Return audit events matching equality ``filters`` (ordered by rowid).

        Only the columns in :data:`_QUERYABLE_FIELDS` may be filtered; an
        unknown field raises :class:`ValueError`. All queries are
        parameterized.
        """
        filters = filters or {}
        clauses: list[str] = []
        params: list[Any] = []
        for field, value in filters.items():
            if field not in _QUERYABLE_FIELDS:
                raise ValueError(f"Not a queryable audit field: {field}")
            clauses.append(f"{field} = ?")
            params.append(value)

        sql = "SELECT * FROM audit_events"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY rowid ASC"

        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_event(row) for row in rows]

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> AuditEvent:
        data = dict(row)
        data["payload"] = json.loads(data["payload"])
        return AuditEvent.model_validate(data)

    def __getattr__(self, name: str) -> Any:
        """Reject mutating method names explicitly (C-11)."""
        if name in _FORBIDDEN_METHODS:
            raise AttributeError(
                f"AuditRepository is append-only; '{name}' is not permitted"
            )
        raise AttributeError(name)


def _self_test() -> None:
    """Append an event, read it back, and confirm no mutation API exists."""
    from compliance_runtime.storage.db import get_connection
    from compliance_runtime.storage.migrate import apply_migrations
    from compliance_runtime.utils.ids import new_ulid, now_utc

    conn = get_connection(":memory:")
    try:
        apply_migrations(conn)
        repo = AuditRepository(conn)
        event = AuditEvent(
            event_id=new_ulid(),
            occurred_at=now_utc(),
            actor_type="system",
            actor_id="system",
            action="self_test",
            entity_type="audit_event",
            entity_id=new_ulid(),
            correlation_id=new_ulid(),
            payload={"n": 1},
        )
        repo.append(event)

        got = repo.query({"action": "self_test"})
        assert len(got) == 1 and got[0].event_id == event.event_id

        for method in ("update", "delete"):
            assert not hasattr(repo, method), method
        print("storage.audit self-test: PASS")
    finally:
        conn.close()


if __name__ == "__main__":
    _self_test()
