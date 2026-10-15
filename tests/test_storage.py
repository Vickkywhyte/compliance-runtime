"""Schema / migration tests (ADR-003, ADR-015)."""

from __future__ import annotations

import sqlite3

from compliance_runtime.storage.db import get_connection
from compliance_runtime.storage.migrate import apply_migrations

_EXPECTED_TABLES = {
    "tool_calls",
    "policy_evaluations",
    "action_records",
    "approval_requests",
    "approval_decisions",
    "audit_events",
    "schema_migrations",
}

_EXPECTED_TRIGGERS = {
    "action_records_no_update",
    "action_records_no_delete",
    "approval_decisions_no_update",
    "approval_decisions_no_delete",
    "audit_events_no_update",
    "audit_events_no_delete",
}


def _fresh() -> sqlite3.Connection:
    conn = get_connection(":memory:")
    apply_migrations(conn)
    return conn


def _names(conn: sqlite3.Connection, kind: str) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = ?", (kind,)
    ).fetchall()
    return {row["name"] for row in rows}


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def test_migration_creates_all_tables() -> None:
    conn = _fresh()
    assert _EXPECTED_TABLES <= _names(conn, "table")


def test_migration_is_idempotent() -> None:
    conn = _fresh()
    before = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    apply_migrations(conn)
    after = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    assert before == after == 1


def test_migration_creates_triggers() -> None:
    conn = _fresh()
    assert _EXPECTED_TRIGGERS <= _names(conn, "trigger")


def test_tool_calls_table_has_correct_columns() -> None:
    conn = _fresh()
    assert _columns(conn, "tool_calls") == {
        "call_id",
        "correlation_id",
        "agent_id",
        "session_id",
        "action",
        "parameters",
        "received_at",
        "metadata",
    }


def test_action_records_table_has_correct_columns() -> None:
    conn = _fresh()
    cols = _columns(conn, "action_records")
    assert cols == {
        "action_id",
        "call_id",
        "evaluation_id",
        "disposition",
        "agent_id",
        "session_id",
        "action",
        "parameters_hash",
        "timestamp",
        "previous_hash",
        "current_hash",
        "signature",
        "signing_key_id",
        "runtime_version",
    }
    # The hash-chain columns specifically must be present.
    assert {"previous_hash", "current_hash", "signature", "signing_key_id"} <= cols
