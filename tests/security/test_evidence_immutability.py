"""Evidence immutability tests (C-10 to C-14).

Append-only is enforced at two layers: SQLite triggers (C-10) and the
repository API (C-11). These tests assert both.
"""

from __future__ import annotations

import sqlite3

import pytest

from compliance_runtime.storage.audit import AuditRepository
from compliance_runtime.storage.db import get_connection
from compliance_runtime.storage.migrate import apply_migrations
from compliance_runtime.storage.models import AuditEvent
from compliance_runtime.utils.ids import new_ulid, now_utc


def _conn() -> sqlite3.Connection:
    conn = get_connection(":memory:")
    apply_migrations(conn)
    return conn


def _event() -> AuditEvent:
    return AuditEvent(
        event_id=new_ulid(),
        occurred_at=now_utc(),
        actor_type="system",
        actor_id="system",
        action="test_event",
        entity_type="audit_event",
        entity_id=new_ulid(),
        correlation_id=new_ulid(),
        payload={"n": 1},
    )


def test_audit_events_append_works() -> None:
    conn = _conn()
    repo = AuditRepository(conn)
    event = _event()
    repo.append(event)
    got = repo.query({"event_id": event.event_id})
    assert len(got) == 1
    assert got[0].payload == {"n": 1}
    conn.close()


def test_direct_sql_update_raises() -> None:
    conn = _conn()
    AuditRepository(conn).append(_event())
    with pytest.raises(sqlite3.Error):
        conn.execute("UPDATE audit_events SET action = 'tampered'")
        conn.commit()
    conn.close()


def test_direct_sql_delete_raises() -> None:
    conn = _conn()
    AuditRepository(conn).append(_event())
    with pytest.raises(sqlite3.Error):
        conn.execute("DELETE FROM audit_events")
        conn.commit()
    conn.close()


def test_repository_has_no_update_method() -> None:
    repo = AuditRepository(_conn())
    assert not hasattr(repo, "update")


def test_repository_has_no_delete_method() -> None:
    repo = AuditRepository(_conn())
    assert not hasattr(repo, "delete")
