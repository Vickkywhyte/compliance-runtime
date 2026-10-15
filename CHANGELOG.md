# Changelog

Newest-first order.

## Phase 2 — Storage + evidence foundations
**2026-10-15 — Completed**

- 11 new files: SQLite migration (001_initial.sql, 128 lines, full
  schema from 05_DATA_SPEC.md §7), migrate.py with schema_migrations
  tracking, 5 repositories (tool_calls, evaluations, action_records,
  approvals), migrate selftest, 2 test files, 1 fixture file
- 3 modified files: exceptions.py (+StorageError, +MigrationError),
  doctor.py (registers 6 new modules -> 19 total), Makefile (real
  migrate target + 02-migrate-selftest)
- Tests: 65 passing (28 -> 63 -> 65)
- All 7 tables from §7 present; all 6 append-only triggers verified
  by direct SQL UPDATE/DELETE rejection
- Every repository has read-back tests (Lesson 5)
- Migration is idempotent (schema_migrations tracking)
- Security controls verified: C-10, C-11, C-14, C-34

Two defects found and fixed during verification:
1. Repositories depended on caller's row_factory; a raw sqlite3.connect
   produced ValueError instead of ChainIntegrityError. Fixed: each
   repository sets self._conn.row_factory = sqlite3.Row in __init__.
   Added 2 regression tests.
2. db.py contained a dead duplicate schema (_SCHEMA + migrate()) that
   diverged from 001_initial.sql. Removed; single source of truth is
   now storage/migrations/*.sql applied via storage/migrate.py.

ADRs applied: ADR-003, ADR-008, ADR-015

## Phase 1 — Scaffolding + safety rails
**2026-10-15 — Completed**

- 32 files: pyproject.toml, requirements.lock (via pip-compile),
  .env.example, .gitignore, .pre-commit-config.yaml, Makefile,
  Dockerfile stub, docker-compose.yml stub
- Package: config/{loader,models,keys}.py, utils/{logging,ids}.py,
  exceptions.py, storage/{db,models,audit}.py
- Configs: runtime.yaml, eval.yaml
- Scripts: doctor.py, selftest.py, check_changelog.py
- Tests: 28 passing (config, logging, ids, security/evidence
  immutability, security/key safety, security/log injection)
- All 12 prevention mechanisms active (Lessons 1, 1b, 2-12)
- Security controls verified: C-07, C-10 to C-14, C-15 to C-20,
  C-28 (structure), C-34, C-41, C-42, C-45, C-46
- ADRs applied: ADR-003, ADR-008, ADR-009, ADR-013, ADR-017

Verification: `make sync && make doctor && make test && make selftest`
-> 13 imports OK, 28 tests passing, 9 module self-tests passing.

Signing key at ~/.compliance-runtime/keys/ with mode 0600 (private) and
0644 (public). `.gitignore` covers `*.pem`, `*.db*`, `.DS_Store`.
