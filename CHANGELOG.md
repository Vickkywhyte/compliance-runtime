# Changelog

Newest-first order.

## Project summary

**Status: COMPLETE** — 11 of 11 phases.

- 11 / 11 phases complete
- 367 tests passing
- 46 security controls cataloged (P0 + P1 + P2) (C-01…C-46)
- 18 ADRs locked (immutable once written)
- 17 evaluation metrics across 4 categories (enforcement, evidence,
  oversight, operational)
- Demo runs end-to-end in < 1 second
- Zero runtime cost ($0)
- Zero LLM dependencies in the runtime

### CI exceptions

- PYSEC-2026-3447 (setuptools, MANIFEST.in sdist) — inapplicable;
  documented in docs/security.md. Project does not publish
  packages or build sdists.

## Phase 11 — Documentation + launch
**2026-10-16 — Completed**

- README.md: public-facing rewrite with TL;DR, architecture, quick
  start, security summary, evaluation explainer, 30-second pitch
- CONTRIBUTING.md: dev setup, conventions, security considerations,
  PR checklist
- LICENSE: MIT (Victor Daniel)
- PROJECT_BIBLE.md: plain-English master reference explaining the
  entire project for non-technical readers while serving as the
  canonical reference for contributors
- docs/screenshots/: placeholder directory (screenshots added
  post-launch)
- Project status: COMPLETE

## Phase 10 — Security hardening + Docker + CI
**2026-10-15 — Completed**

- 8 new/finalized files: Dockerfile (multi-stage, non-editable
  install), docker-compose.yml (runtime service with TCP healthcheck),
  .dockerignore (excludes .env, *.pem, *.db*), .gitattributes
  (line-ending normalization), .github/workflows/ci.yml (3 jobs: test,
  security-audit with pip-audit, docker-build smoke), .github/
  pull_request_template.md (security checklist), docs/security.md
  (public-facing threat model summary), tests/security/
  test_dependency_pinning.py (7 tests, C-41 to C-44)
- 1 modified file: Makefile (+docker-build, +docker-up, +docker-down,
  +compose-config; removed dead `dossier` stub)
- Tests: 367 passing (was 360)

Docker:
- Multi-stage build; builder installs deps from requirements.lock and
  the project non-editable; runtime copies site-packages + app code
- No torch, no unstructured, no chromadb, no libmagic1 — the runtime
  is pure Python (verified by import grep)
- Image size target: < 500 MB (down from the previous projects' < 3 GB
  because the runtime has no ML dependencies)
- Non-root user (uid 1000)
- .dockerignore excludes .env, *.pem, *.db* sidecars

CI:
- 3 jobs: test (pytest), security-audit (pip-audit --strict), 
  docker-build (build image + smoke test /)
- Test job installs from lockfile, then dev deps (C-32 / C-44)

Security:
- C-41 (pinned deps via pip-compile), C-42 (maintained packages),
  C-43 (pip-audit in CI), C-44 (lockfile-only CI install)
- 7 dependency-pinning tests: lock exists, pins exact versions, no
  local paths, all runtime deps declared, no drift, CI exists, CI
  has docker build

Significant deviation from the Phase 10 prompt flagged and resolved:
The prompt referenced torch / libmagic1 / HuggingFace cache from a
prior project's Dockerfile. Verified: this project's runtime imports
zero ML libraries (cryptography, pydantic, fastapi, streamlit,
structlog, reportlab, numpy, pyyaml, ulid, python-dotenv only). The
Dockerfile is built for the actual pure-Python dependency set —
smaller image, no wasted layers.

ADRs applied: ADR-013 (no LLM in critical path)

## Phase 9 — Dossier generator + mock agent + demo
**2026-10-15 — Completed**

- 16 new files: dossier package (generator with reportlab PDF, EU AI
  Act Article 12 obligation mapping, HTML template), mock agent
  package (agent + runner), 3 demo scripts, demo CLI, dossier
  selftest, 4 test files
- 3 modified files: exceptions.py (+DemoError), doctor.py (+6 modules
  -> 78), Makefile (real demo + demo-noserve + dossier-selftest)
- Tests: 360 passing (was 329)

Functionality:
- DossierGenerator reads ActionRecords + ApprovalRequests +
  ApprovalDecisions and produces a regulator-ready PDF mapping
  evidence to EU AI Act Article 12 (art12.1, art12.2, art12.3) and
  Article 14 (human oversight) obligations
- MockAgent reads scripted tool-call JSON and executes each via
  ToolExecutor — no LLM
- make demo-noserve runs 3 scripts / 6 steps end-to-end in under 1
  second, producing 4 allow / 1 deny / 1 require_approval, and a
  dossier PDF

Security (C-37, C-38, C-39, C-40):
- Dossier field whitelist enforced (C-38); raw parameters never
  included (C-37); private key never in PDF (C-39); verification key
  fingerprint present but never the key material (C-40)
- PDF uncompressed (pageCompression=0) so export-safety audits can
  grep raw bytes
- Dossier field whitelist test + 6 export-safety tests pass

Verified:
- Demo completes in ~0.42s (< 60s target)
- Mock agent deterministic across runs
- Disposition mix exactly 4 allow / 1 deny / 1 require_approval
- Zero LLM/HTTP imports in demo path (ADR-013)
- All 4 EU AI Act obligations marked "satisfied"

Three fixes applied during verification:
1. Dossier per-action rows now include matched_rule_id (joined from
   policy_evaluations).
2. approval_summary respects the since/until range (was all-time).
3. Repository-level list_in_range added to support (2).

ADRs applied: ADR-004, ADR-006, ADR-013

## Phase 8 — Dashboard (Streamlit)
**2026-10-15 — Completed**

- 16 new files: dashboard package (app, state, theme, 4 views,
  4 components), dashboard selftest, dashboard views test
- 3 modified files: interception/pipeline.py (+all_action_records,
  +get_tool_call read-only accessors), doctor.py (+14 modules -> 72),
  Makefile (+serve-dashboard, +dashboard-selftest; serve unchanged)
- Tests: 329 passing (was 321)

Views:
- Live Actions: filterable table of tool calls + dispositions with
  drill-down to policy evaluation, action record, and evidence link
- Approvals: pending requests filtered by role, approve/edit+approve/
  reject actions routed through pipeline.decide_approval
- Evidence Chain: paginated table of ActionRecords with hash truncation;
  verify-one + verify-all actions
- Compliance Summary: reads results/evals/*.json, shows 4 CI-eligible
  summary cards + full 17-metric table

Security:
- C-06 (HTML escape): single safe() helper wraps html.escape; audit
  found no unescaped display sites for user/DB data
- C-30 (policy hash): sidebar shows content_hash
- No repository bypass: static check + line-grep confirm dashboard
  imports no storage repositories; single decision site is
  pipeline.decide_approval
- Selftest is hermetic: MagicMock streamlit, real in-memory pipeline,
  no browser, no network

Verified:
- Every render function callable via mocked streamlit
- test_safe_escapes_html: '<script>' -> '&lt;script&gt;'
- test_approval_form_uses_pipeline: import-graph guard passes
- Badge colors distinct per disposition (4) and severity (4)
- 8 dashboard view tests + 11 selftest assertions pass

ADRs applied: ADR-012 (Streamlit dashboard), ADR-007 (approval
locking preserved — no UI bypass)

Note: app.py reads pipeline._engine._policy_set (read-only) for the
sidebar policy panel. This is the third read-only private-attribute
access in the project (after Phase 5's repo._conn and Phase 6's
approval_service._requests). A v2 refactor to expose a public
pipeline.policy_set property is noted as a code-quality improvement.

## Phase 7 — Evaluation harness
**2026-10-15 — Completed**

- 19 new files: evaluation package (Metric ABC, 4 metric modules
  covering 17 metrics, benchmark loader + quality gate, runner,
  report, stats, registry), 2 scripts (07_eval, 07_eval_selftest),
  4 test files, 2 fixture files (metrics_cases.json, benchmark_mini.jsonl)
- 5 modified files: exceptions.py (+EvalError, +BenchmarkValidationError),
  interception/pipeline.py (+verify_chain_for, +get_evaluations_for_call),
  pyproject.toml (+numpy>=1.26), doctor.py (+11 modules -> 58),
  Makefile (real eval, eval-mini, 07-eval-selftest)
- 2 spec updates to 06_EVAL_SPEC.md: §6 documents evidence_write_p50_ms
  as a proxy; §7 JSON key renamed to aggregate_metrics; §8 CI list
  reduced to the 7 metrics with well-defined per-entry means
- Tests: 321 passing (was 275)

Metrics implemented (17 total):
- Enforcement (5): policy_precision, policy_recall, false_positive_rate,
  false_negative_rate, policy_coverage
- Evidence (3): audit_completeness, chain_integrity, signature_validity
- Oversight (5): approval_latency_p50_ms, approval_latency_p95_ms,
  approval_rate, override_rate, auto_deny_rate
- Operational (4): runtime_overhead_p50_ms, policy_eval_p50_ms,
  evidence_write_p50_ms (proxy), cost_per_1k_actions_usd

Verified:
- Every metric has positive + negative fixtures (06_EVAL_SPEC §9)
- Quality gate catches 8 failure modes
- bootstrap_ci deterministic with fixed seed, handles list + numpy,
  raises on empty input
- Two runs of `make eval-mini` produce identical deterministic metrics
  (11 metrics compared; timing metrics excluded by design)
- aggregate_ci contains exactly the 7 CI-eligible metrics
- chain_integrity = 1.0 and signature_validity = 1.0 on mini benchmark
- Zero LLM/HTTP imports in evaluation path (ADR-013)
- Eval is hermetic (temp DB + temp key dir)

ADRs applied: ADR-011, ADR-012

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
