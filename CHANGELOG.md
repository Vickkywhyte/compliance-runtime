# Changelog

Newest-first order.

## Phase 6 — Interception layer (HTTP + SDK)
**2026-10-15 — Completed**

- 18 new files: interception package (models, openai_compat, pipeline,
  sdk, server), dispositions package (allow, deny, approval, flagged,
  dispatcher), runtime selftest, 5 test files, 1 fixture file
- 4 modified files: policy/models.py (+matched_rule_enforcement on
  EvaluationResult), policy/engine.py (populates it on match),
  scripts/doctor.py (+11 modules -> 47), Makefile (real serve target
  + 06-runtime-selftest)
- Tests: 275 passing (was 234)

Functionality:
- RuntimePipeline: ToolCall -> policy eval -> evidence -> disposition
  -> (approval request if needed) -> RuntimeResponse
- Python SDK: ToolExecutor.from_config + execute + context manager
- FastAPI server: /health, /v1/tools/execute, /v1/tools/execute-openai,
  /v1/approvals*, /v1/evidence*, all async
- OpenAI-compatible function call parsing + response serialization
- Four disposition handlers are pure (no I/O); tested
- Determinism verified: same input -> same disposition + matched_rule_id

Verified:
- Allow path writes tool_call + policy_evaluation + action_record;
  chain integrity 1.0
- Deny path returns structured error with rule_id
- require_approval creates real ApprovalRequest with assignee_role
  and severity sourced from matched_rule_enforcement
- Same input -> same disposition; unique action_ids per call
- Zero LLM SDK imports (ADR-013)
- Error envelope: 422 on bad input, no traceback leaked

ADRs applied: ADR-002, ADR-006, ADR-010, ADR-011, ADR-013, ADR-018

## Phase 5 — Approval workflow
**2026-10-15 — Completed**

- 10 new files: approvals package (state machine, TTL, service),
  approval selftest, 3 test files (service, state, ttl), 1 shared
  tests/conftest.py fixture, 1 security test file (approval_integrity
  with 10 tests including two real-thread concurrency tests)
- 4 modified files: storage/approvals.py (+update_state_with_lock,
  +get_by_id_with_version, +commit flag), storage/audit.py (+commit
  flag for same-transaction participation), scripts/doctor.py
  (+4 modules -> 36), Makefile (+approve-selftest target)
- Tests: 234 passing (was 191)
- State machine: pending -> {approved, denied, modified_approved,
  expired}; all four are terminal
- Optimistic locking: WHERE version = ? AND state = 'pending' inside
  BEGIN IMMEDIATE ... COMMIT
- 5-thread concurrency test: exactly 1 winner, 4 ConcurrentModificationError,
  stable over 5 re-runs
- Audit event written in the same transaction as decision + state change
  (C-23)
- Expired requests cannot be approved (C-26)
- Terminal states cannot be transitioned (C-24)
- Atomicity proof: 3 decides on different states -> exactly 1 decision row,
  exactly 2 audit events (requested + decided)

Security controls verified: C-21, C-22, C-23, C-24, C-25, C-26, C-27

Note: storage/audit.py was modified outside the explicit MODIFY list to
add a `commit: bool = True` keyword to AuditRepository.append. Required
for audit events to participate in the same transaction as the state
change (C-23). Backward compatible — all Phase 1-4 callers still pass
with default auto-commit.

ADRs applied: ADR-007, ADR-015

## Phase 4 — Evidence recorder + verifier
**2026-10-15 — Completed**

- 11 new files: evidence package (hashing, signing, recorder,
  verifier), evidence selftest, 4 test files, known-answer hash
  vectors fixture
- 5 modified files: config/keys.py (+set_keys_dir/get_keys_dir
  override), storage/action_records.py (+list_all/list_range
  read-only), tests/security/test_key_safety.py (+3 signing-safety
  tests), scripts/doctor.py (+5 modules -> 32), Makefile (real verify
  target + 04-evidence-selftest)
- Tests: 191 passing (was 152)
- SHA-256 hash chain + Ed25519 signatures on every ActionRecord
- parameters_hash = sha256(canonical_json(parameters)) — raw values
  never stored (C-37)
- Verifier works offline; verify_records exposed for synthetic testing
- Chain order = rowid (insertion order), NOT action_id — ulid-py is
  not monotonic within a millisecond
- signing_key_id included in hashed payload (recorder + verifier
  hash identical field dict)
- Raw ed25519 private-key primitive confined to config/keys.py only
  (C-18, tighter than spec)
- Security controls verified: C-10..C-14, C-15..C-20, C-35, C-37

Known-answer vectors (5) confirm canonicalization stability across:
sorted keys, nested structures, unicode, float precision, datetime.

ADRs applied: ADR-004, ADR-017

## Phase 3 — Policy engine
**2026-10-15 — Completed**

- 18 new files: policy package (models, loader, validators, engine,
  field_resolver, rate_limit, injection), demo_policy.yaml,
  policy selftest, 5 test files (loader, validator, engine, field
  resolver, rate limit), 3 security test files (policy_bypass with 15
  scenarios, injection with 15 scenarios, policy_integrity)
- 2 modified files: scripts/doctor.py (+8 modules -> 27), Makefile
  (real policy-validate target + 03-policy-selftest)
- 1 spec clarification: 05_DATA_SPEC.md §3.7 documents that
  PolicySet.content_hash is a SEMANTIC hash (parsed representation,
  not raw file bytes)
- Tests: 152 passing (was 65). 58 in tests/security/.
- Priority-ordered evaluation, first match wins
- Four dispositions: allow, deny, require_approval, allow_with_flag
- 15 policy bypass scenarios pass (C-05)
- 15 injection scenarios pass (C-08, C-09)
- Rate limiter: 100/min per agent+action, drops metric (C-32, C-36)
- PolicySet.version embeds content_hash[:8] (C-29)
- Security controls verified: C-01..C-05, C-08, C-09, C-28, C-29,
  C-31, C-32, C-33, C-36

Two defects found and fixed during verification:
1. C-31 (refuse to start on policy error) was only half-enforced:
   semantic validation (empty when, duplicate priorities, invalid field
   patterns) was not called on the load path. Fixed: load_policy_set
   and PolicyEngine.__init__ both call validate_policy. 5 regression
   tests added.
2. Verified that content_hash semantics (parsed vs. byte-level) were
   a deliberate design decision; documented explicitly in
   05_DATA_SPEC.md §3.7.

ADRs applied: ADR-005, ADR-006, ADR-013, ADR-014

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
