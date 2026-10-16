"""SQLite connection management (ADR-003).

Schema is defined solely in ``storage/migrations/*.sql`` and applied via
``storage/migrate.py``. :func:`get_connection` returns a configured SQLite
connection; it does NOT apply migrations — call
``compliance_runtime.storage.migrate.apply_migrations`` for that.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

_DEFAULT_DB_PATH = "data/runtime.db"


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection in WAL mode with foreign keys enforced.

    Pass ``":memory:"`` for an ephemeral database. A file path's parent
    directory is created if needed. Rows are returned as ``sqlite3.Row``.
    This does NOT create the schema; see ``storage/migrate.py``.
    """
    path = db_path or _DEFAULT_DB_PATH
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False is required because Streamlit re-runs
    # app.py on a fresh thread per interaction and the pipeline is
    # cached via st.cache_resource. WAL mode + single-writer pattern
    # (BEGIN IMMEDIATE) make this safe for v1. A connection-per-
    # request design is a v1.1 concern.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def table_names(conn: sqlite3.Connection) -> set[str]:
    """Return the set of user table names in the database."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {row["name"] for row in rows}


def _self_test() -> None:
    """Open a connection, apply migrations, and confirm every table exists."""
    # Schema lives in storage/migrations/*.sql, applied by storage/migrate.py.
    from compliance_runtime.storage.migrate import apply_migrations

    conn = get_connection(":memory:")
    try:
        apply_migrations(conn)
        apply_migrations(conn)  # idempotent
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
