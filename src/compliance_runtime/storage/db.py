"""SQLite connection management and schema migration (ADR-003).

- :func:`get_connection` opens a WAL-mode connection with foreign keys on.
- :func:`migrate` applies the full schema from ``05_DATA_SPEC.md`` §7,
  including the append-only triggers (C-10), idempotently.

The schema here is the single source of truth for Phase 1. Phase 2 moves
it into numbered migration files; until then the DDL is embedded so the
append-only guarantees can be tested from Phase 1 (per the roadmap).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

# Full DDL — 05_DATA_SPEC.md §7. Wrapped in IF NOT EXISTS so migrate() is
# idempotent (re-running is a no-op).
_SCHEMA = """
CREATE TABLE IF NOT EXISTS tool_calls (
    call_id TEXT PRIMARY KEY,
    correlation_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    action TEXT NOT NULL,
    parameters TEXT NOT NULL,           -- JSON
    received_at TEXT NOT NULL,
    metadata TEXT
);
CREATE INDEX IF NOT EXISTS idx_calls_correlation ON tool_calls(correlation_id);
CREATE INDEX IF NOT EXISTS idx_calls_agent ON tool_calls(agent_id);

CREATE TABLE IF NOT EXISTS policy_evaluations (
    evaluation_id TEXT PRIMARY KEY,
    call_id TEXT NOT NULL,
    matched_rule_id TEXT,
    matched_rule_priority INTEGER,
    policy_version TEXT NOT NULL,
    disposition TEXT NOT NULL,
    reason TEXT NOT NULL,
    evidence TEXT NOT NULL,             -- JSON
    evaluated_at TEXT NOT NULL,
    evaluation_duration_ms INTEGER NOT NULL,
    FOREIGN KEY (call_id) REFERENCES tool_calls(call_id)
);

CREATE TABLE IF NOT EXISTS action_records (
    action_id TEXT PRIMARY KEY,
    call_id TEXT NOT NULL,
    evaluation_id TEXT NOT NULL,
    disposition TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    action TEXT NOT NULL,
    parameters_hash TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    current_hash TEXT NOT NULL,
    signature TEXT NOT NULL,
    signing_key_id TEXT NOT NULL,
    runtime_version TEXT NOT NULL,
    FOREIGN KEY (call_id) REFERENCES tool_calls(call_id),
    FOREIGN KEY (evaluation_id) REFERENCES policy_evaluations(evaluation_id)
);
CREATE INDEX IF NOT EXISTS idx_records_timestamp ON action_records(timestamp);

-- Append-only enforcement (ADR-015, C-10)
CREATE TRIGGER IF NOT EXISTS action_records_no_update
BEFORE UPDATE ON action_records
BEGIN
    SELECT RAISE(ABORT, 'action_records is append-only');
END;
CREATE TRIGGER IF NOT EXISTS action_records_no_delete
BEFORE DELETE ON action_records
BEGIN
    SELECT RAISE(ABORT, 'action_records is append-only');
END;

CREATE TABLE IF NOT EXISTS approval_requests (
    request_id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL,
    call_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    matched_rule_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    assignee_role TEXT NOT NULL,
    ttl_seconds INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    state TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (action_id) REFERENCES action_records(action_id)
);
CREATE INDEX IF NOT EXISTS idx_approvals_state_role
    ON approval_requests(state, assignee_role);

CREATE TABLE IF NOT EXISTS approval_decisions (
    decision_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    decision TEXT NOT NULL,
    edits TEXT,                          -- JSON, nullable
    rationale TEXT,
    decided_at TEXT NOT NULL,
    FOREIGN KEY (request_id) REFERENCES approval_requests(request_id)
);

CREATE TRIGGER IF NOT EXISTS approval_decisions_no_update
BEFORE UPDATE ON approval_decisions
BEGIN
    SELECT RAISE(ABORT, 'approval_decisions is append-only');
END;
CREATE TRIGGER IF NOT EXISTS approval_decisions_no_delete
BEFORE DELETE ON approval_decisions
BEGIN
    SELECT RAISE(ABORT, 'approval_decisions is append-only');
END;

CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    occurred_at TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    payload TEXT NOT NULL                -- JSON
);
CREATE INDEX IF NOT EXISTS idx_audit_entity
    ON audit_events(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_correlation
    ON audit_events(correlation_id);

CREATE TRIGGER IF NOT EXISTS audit_events_no_update
BEFORE UPDATE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events is append-only');
END;
CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
BEFORE DELETE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events is append-only');
END;
"""

_DEFAULT_DB_PATH = "data/runtime.db"


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection in WAL mode with foreign keys enforced.

    Pass ``":memory:"`` for an ephemeral database. A file path's parent
    directory is created if needed. Rows are returned as ``sqlite3.Row``.
    """
    path = db_path or _DEFAULT_DB_PATH
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    """Apply the full schema idempotently."""
    conn.executescript(_SCHEMA)
    conn.commit()


def table_names(conn: sqlite3.Connection) -> set[str]:
    """Return the set of user table names in the database."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {row["name"] for row in rows}


def _self_test() -> None:
    """Migrate an in-memory DB and confirm every table exists; re-run safe."""
    conn = get_connection(":memory:")
    try:
        migrate(conn)
        migrate(conn)  # idempotent
        expected = {
            "tool_calls",
            "policy_evaluations",
            "action_records",
            "approval_requests",
            "approval_decisions",
            "audit_events",
        }
        names = table_names(conn)
        assert expected <= names, expected - names
        print("storage.db self-test: PASS")
    finally:
        conn.close()


if __name__ == "__main__":
    _self_test()
