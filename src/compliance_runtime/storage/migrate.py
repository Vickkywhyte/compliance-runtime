"""Schema migration runner (ADR-003, 05_DATA_SPEC §10).

Applies the numbered ``*.sql`` files in ``storage/migrations/`` in order,
tracking applied versions in a ``schema_migrations`` table so that re-runs
are idempotent. Each migration runs inside an explicit
``BEGIN IMMEDIATE`` / ``COMMIT`` transaction, so a failure leaves the
schema unchanged.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from compliance_runtime.exceptions import MigrationError
from compliance_runtime.utils.ids import now_utc

_MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

_SCHEMA_MIGRATIONS_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""


def _migration_files() -> list[Path]:
    """Return migration ``.sql`` files sorted by numeric prefix."""
    return sorted(_MIGRATIONS_DIR.glob("[0-9]*.sql"), key=lambda p: p.name)


def _ensure_tracking_table(conn: sqlite3.Connection) -> None:
    conn.execute(_SCHEMA_MIGRATIONS_DDL)
    conn.commit()


def migration_status(conn: sqlite3.Connection) -> list[str]:
    """Return applied migration versions in ascending order."""
    _ensure_tracking_table(conn)
    rows = conn.execute(
        "SELECT version FROM schema_migrations ORDER BY version ASC"
    ).fetchall()
    return [row[0] for row in rows]


def _apply_one(conn: sqlite3.Connection, path: Path) -> None:
    """Apply a single migration file atomically (BEGIN IMMEDIATE/COMMIT)."""
    version = path.stem
    applied_at = now_utc().isoformat()
    sql = path.read_text(encoding="utf-8")

    # Settle any pending autocommit transaction so the explicit BEGIN below
    # is the only transaction executescript runs.
    if conn.in_transaction:
        conn.commit()

    # executescript performs no implicit transaction control of its own, so
    # the BEGIN IMMEDIATE / COMMIT we add make the whole migration atomic.
    script = (
        "BEGIN IMMEDIATE;\n"
        + sql
        + "\nINSERT INTO schema_migrations (version, applied_at) "
        + f"VALUES ('{version}', '{applied_at}');\n"
        + "COMMIT;\n"
    )
    try:
        conn.executescript(script)
    except sqlite3.Error as exc:
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        raise MigrationError(f"Migration {version} failed: {exc}") from exc


def apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply all pending migrations in order. Idempotent."""
    if not _MIGRATIONS_DIR.is_dir():
        raise MigrationError(f"Migrations directory not found: {_MIGRATIONS_DIR}")

    _ensure_tracking_table(conn)
    applied = set(migration_status(conn))

    for path in _migration_files():
        version = path.stem
        if version in applied:
            continue
        _apply_one(conn, path)


def _self_test() -> None:
    """Apply migrations to an in-memory DB and verify idempotency."""
    conn = sqlite3.connect(":memory:")
    try:
        apply_migrations(conn)
        count = conn.execute(
            "SELECT COUNT(*) FROM schema_migrations"
        ).fetchone()[0]
        assert count == 1, f"expected 1 migration row, got {count}"

        apply_migrations(conn)  # re-apply must be a no-op
        count_again = conn.execute(
            "SELECT COUNT(*) FROM schema_migrations"
        ).fetchone()[0]
        assert count_again == 1, f"idempotency broken: {count_again} rows"

        assert migration_status(conn) == ["001_initial"], migration_status(conn)
        print("PASS")
    finally:
        conn.close()


if __name__ == "__main__":
    _self_test()
