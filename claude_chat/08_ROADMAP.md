# Roadmap — AI Compliance Runtime

> **READ THIS FIRST (for Claude Code):**
> Work one phase at a time, in order. Do not start Phase N+1 until
> Phase N's checkpoint passes AND the phase-tracker agent has closed
> Phase N. Every phase has a prevention mechanism from
> `01_LESSONS_APPLIED.md` wired in.
>
> **Dependencies:** All Stage 0 docs
> **Depended on by:** `09_RUNTIME_DESIGN.md` · `CLAUDE.md`

---

## Overview

| # | Phase | Est. effort | Depends on |
|---|---|---|---|
| 1 | Scaffolding + safety rails | 0.5 day | — |
| 2 | Storage + evidence foundations | 1.5 days | 1 |
| 3 | Policy engine | 2 days | 2 |
| 4 | Evidence recorder + verifier | 2 days | 3 |
| 5 | Approval workflow | 2 days | 4 |
| 6 | Interception layer (HTTP + SDK) | 1.5 days | 5 |
| 7 | Evaluation harness | 2 days | 5 |
| 8 | Dashboard | 1.5 days | 6 |
| 9 | Dossier generator + mock agent + demo | 2 days | 8 |
| 10 | Security hardening + Docker + CI | 1.5 days | 9 |
| 11 | Documentation + launch | 1 day | 10 |
| | **Total** | **~17.5 days** | |

**Legend:** 🟢 done · 🟡 in progress · ⚪ not started · 🔴 blocked

**Note:** The compliance runtime is deeper than the prior two projects.
Estimated effort is longer because of the cryptographic attestation,
the four-disposition state machine, and the approval workflow. That's
realistic, not padding.

---

## Phase 1 — Scaffolding + safety rails 🟢

**Goal:** Cloneable repo with prevention mechanisms from Lessons 1, 1b,
5, 7, 8, 9, 11, 12 in place. No application logic yet.

**Deliverables:**
```
pyproject.toml
requirements.lock
.env.example
.gitignore
.pre-commit-config.yaml
Makefile
docker-compose.yml                # stub
Dockerfile                        # stub
src/compliance_runtime/__init__.py
src/compliance_runtime/config/__init__.py
src/compliance_runtime/config/loader.py
src/compliance_runtime/config/models.py
src/compliance_runtime/config/keys.py
src/compliance_runtime/utils/__init__.py
src/compliance_runtime/utils/logging.py
src/compliance_runtime/utils/ids.py
src/compliance_runtime/exceptions.py
src/compliance_runtime/storage/__init__.py
src/compliance_runtime/storage/db.py
src/compliance_runtime/storage/models.py
src/compliance_runtime/storage/audit.py
configs/runtime.yaml
configs/eval.yaml
scripts/doctor.py
scripts/selftest.py
tests/__init__.py
tests/test_config.py
tests/test_logging.py
tests/test_ids.py
tests/security/__init__.py
tests/security/test_evidence_immutability.py
tests/security/test_key_safety.py
tests/security/test_log_injection.py
```

**Prevention mechanisms active:**
- Lesson 1: `make sync` + `make doctor`
- Lesson 1b: `grep FAILED|ERROR` verification pattern
- Lesson 5: logging read-back test
- Lesson 7: CHANGELOG pre-commit hook
- Lesson 8: `config/loader.py` is the only place `os.getenv` lives
- Lesson 9: DoD evidence requirements (from Phase 1)
- Lesson 11: `requirements.lock` via `pip-compile`
- Lesson 12: `.gitignore` covers `*.db`, `*.db-shm`, `*.db-wal`,
  `*.db-journal`, `*.pem`

**Security controls active:**
- C-07: control character escaping in logs
- C-10 to C-14: SQLite append-only triggers, direct SQL tests
- C-15 to C-20: key isolation, `.gitignore`, mode 0600, no key in logs
- C-28: policies git-versioned (structure ready)
- C-34: bounded SQLite write queue (connection pool ready)
- C-41, C-42: pinned deps, maintained packages
- C-45, C-46: JSON log escaping + log injection test

**Acceptance criteria:**
- `make sync` installs deps; `make doctor` reports all imports OK
- `make test` runs and passes
- `make selftest` runs every module's `__main__` block
- Logging writes JSON to `logs/app.jsonl` and read-back test passes
- `.env` and `*.pem` are gitignored
- Ed25519 key generation works on first run; key file mode is 0600
- `audit_events` table rejects UPDATE and DELETE (test passes)
- A malformed config raises `ConfigError`
- `grep FAILED|ERROR` returns empty after `make test`

**Checkpoint:**
```bash
make sync && make doctor && make test && make selftest
```

**Risks:**
- `cryptography` library version mismatches; pin the version
- Ed25519 key generation on headless macOS may differ; test

---

## Phase 2 — Storage + evidence foundations 🟢

**Goal:** SQLite schema, repositories for tool calls and evaluations.
Evidence tables defined. No signing yet.

**Deliverables:**
```
src/compliance_runtime/storage/migrations/001_initial.sql
src/compliance_runtime/storage/tool_calls.py
src/compliance_runtime/storage/evaluations.py
src/compliance_runtime/storage/action_records.py    # repository only
src/compliance_runtime/storage/approvals.py         # repository only
src/compliance_runtime/storage/audit.py             # append-only
src/compliance_runtime/storage/migrate.py
scripts/02_migrate_selftest.py
tests/test_storage.py
tests/test_repositories.py
tests/fixtures/sample_records.json
```

**Prevention mechanisms active:**
- Lesson 5: read-back tests for every repository
- Lesson 3: behavior-only assertions

**Security controls active:**
- C-10, C-11: SQLite triggers, repository append-only
- C-14: direct SQL test

**Acceptance criteria:**
- `migrate.py` applies the schema idempotently
- Every repository has read-back tests
- `action_records` update/delete attempts raise
- `approval_decisions` and `audit_events` update/delete attempts raise

**Checkpoint:**
```bash
make migrate && python scripts/02_migrate_selftest.py && pytest tests/test_storage.py tests/test_repositories.py -v
```

---

## Phase 3 — Policy engine 🟢

**Goal:** Load YAML policies, validate, evaluate tool calls against
rules in priority order.

**Deliverables:**
```
src/compliance_runtime/policy/__init__.py
src/compliance_runtime/policy/models.py
src/compliance_runtime/policy/loader.py
src/compliance_runtime/policy/validators.py
src/compliance_runtime/policy/engine.py
configs/policies/demo_policy.yaml
scripts/03_policy_selftest.py
tests/test_policy_loader.py
tests/test_policy_validator.py
tests/test_policy_engine.py
tests/security/test_policy_bypass.py         # C-05: 15 scenarios
tests/security/test_injection.py             # C-08, C-09
tests/security/test_rate_limit.py            # C-32, C-33, C-36
tests/security/test_policy_integrity.py      # C-28, C-29, C-31
```

**Prevention mechanisms active:**
- Lesson 3: behavior-only tests
- Lesson 6: rate-limiter uses async
- Lesson 4: policy quality gate (validate on load)

**Security controls active:**
- C-01 to C-05: schema validation, strict types, action whitelist
- C-08, C-09: injection filter
- C-28, C-29, C-31: policy versioning, hash, refuse to start on error
- C-32, C-33, C-36: rate limiter, size limit, dropped metrics

**Acceptance criteria:**
- YAML policies load and validate
- Priority-ordered evaluation, first match wins
- Four dispositions: allow, deny, require_approval, allow_with_flag
- All 15 policy bypass scenarios in `test_policy_bypass.py` are denied
- Injection filter rejects markers and returns deny
- Rate limiter caps per-agent request rate
- Policy hash recorded in every evaluation
- Runtime refuses to start with invalid policy

**Checkpoint:**
```bash
make policy-validate && pytest tests/test_policy_engine.py tests/security/ -v
```

**Risks:**
- Condition field access on nested JSON (e.g., `parameters.amount`)
  requires careful implementation; add fuzzing

---

## Phase 4 — Evidence recorder + verifier 🟢

**Goal:** Sign and hash-chain every action record; verify chain and
signatures.

**Deliverables:**
```
src/compliance_runtime/evidence/__init__.py
src/compliance_runtime/evidence/hashing.py
src/compliance_runtime/evidence/signing.py
src/compliance_runtime/evidence/recorder.py
src/compliance_runtime/evidence/verifier.py
scripts/04_evidence_selftest.py
tests/test_hashing.py
tests/test_signing.py
tests/test_recorder.py
tests/test_verifier.py
tests/security/test_key_safety.py            # extend
tests/fixtures/known_hash_vectors.json
```

**Prevention mechanisms active:**
- Lesson 3: verify with known-answer tests

**Security controls active:**
- C-12: SHA-256 hash chain
- C-13: Ed25519 signatures
- C-15 to C-20: key isolation, never logged
- C-35: fast evidence writes (< 20 ms p50)
- C-37: `parameters_hash` not raw parameters

**Acceptance criteria:**
- Signing key generated on first run if missing
- Private key file mode is 0600
- `current_hash` computed from canonical JSON + previous_hash
- Signature verifies with public key
- `verifier.verify()` returns a report with chain integrity = 1.0
- Tampering a record's fields breaks verification
- Private key does not appear in `logs/app.jsonl` (test)
- Public key exported and marked
- Evidence write latency p50 < 20 ms (benchmark test)

**Checkpoint:**
```bash
python scripts/04_evidence_selftest.py && pytest tests/test_recorder.py tests/test_verifier.py tests/security/test_key_safety.py -v
```

**Risks:**
- Canonical JSON serialization must be deterministic; test with
  floats, unicode, nested structures
- Ed25519 library API differences; test on target Python version

---

## Phase 5 — Approval workflow 🟢

**Goal:** Create approval requests, transition with optimistic locking,
expire on TTL.

**Deliverables:**
```
src/compliance_runtime/approvals/__init__.py
src/compliance_runtime/approvals/service.py
src/compliance_runtime/approvals/state.py
src/compliance_runtime/approvals/ttl.py
scripts/05_approval_selftest.py
tests/test_approval_service.py
tests/test_approval_state.py
tests/test_approval_ttl.py
tests/security/test_approval_integrity.py    # C-21 to C-27
```

**Prevention mechanisms active:**
- Lesson 3: state machine tested via observable transitions

**Security controls active:**
- C-21 to C-27: single-writer, optimistic lock, audit in same
  transaction, terminal states, concurrent test, expiry check

**Acceptance criteria:**
- `ApprovalService.approve/deny/modify` all work; use optimistic lock
- Concurrent approval attempts: exactly one winner (5 threads test)
- Terminal states reject further transitions
- Expired requests auto-deny
- Every transition writes an `AuditEvent` in the same transaction
- `scripts/05_approval_selftest.py` passes all assertions

**Checkpoint:**
```bash
python scripts/05_approval_selftest.py && pytest tests/security/test_approval_integrity.py -v
```

---

## Phase 6 — Interception layer (HTTP + SDK) 🟢

**Goal:** Expose the runtime over HTTP and as a Python SDK.

**Deliverables:**
```
src/compliance_runtime/interception/__init__.py
src/compliance_runtime/interception/models.py
src/compliance_runtime/interception/server.py         # FastAPI
src/compliance_runtime/interception/sdk.py            # Python SDK
src/compliance_runtime/interception/openai_compat.py  # schema adapter
src/compliance_runtime/dispositions/__init__.py
src/compliance_runtime/dispositions/allow.py
src/compliance_runtime/dispositions/deny.py
src/compliance_runtime/dispositions/approval.py
src/compliance_runtime/dispositions/flagged.py
scripts/06_runtime_selftest.py
tests/test_server.py
tests/test_sdk.py
tests/test_dispositions.py
tests/fixtures/openai_tool_call_examples.json
```

**Prevention mechanisms active:**
- Lesson 2: `--self-test` on server and SDK
- Lesson 3: observable behavior assertions

**Acceptance criteria:**
- HTTP `POST /v1/tools/execute` accepts OpenAI-compatible tool call
- Response is OpenAI-compatible tool response
- Python SDK `ToolExecutor.execute()` runs in-process with same code
  path
- All four dispositions produce correct responses
- `scripts/06_runtime_selftest.py` passes

**Checkpoint:**
```bash
python scripts/06_runtime_selftest.py && pytest tests/test_server.py tests/test_sdk.py -v
```

---

## Phase 7 — Evaluation harness 🟢

**Goal:** Benchmark dataset + metric implementations + report.

**Deliverables:**
```
src/compliance_runtime/evaluation/__init__.py
src/compliance_runtime/evaluation/metrics/__init__.py
src/compliance_runtime/evaluation/metrics/base.py
src/compliance_runtime/evaluation/metrics/enforcement.py
src/compliance_runtime/evaluation/metrics/evidence.py
src/compliance_runtime/evaluation/metrics/oversight.py
src/compliance_runtime/evaluation/metrics/operational.py
src/compliance_runtime/evaluation/runner.py
src/compliance_runtime/evaluation/report.py
src/compliance_runtime/evaluation/stats.py
src/compliance_runtime/evaluation/benchmark.py         # loader + quality gate
scripts/07_eval.py
scripts/07_eval_selftest.py
tests/test_metrics.py
tests/test_stats.py
tests/test_benchmark_gate.py
tests/fixtures/metrics_cases.json
```

**Prevention mechanisms active:**
- Lesson 4: benchmark quality gate runs during curation
- Lesson 3: fixtures for every metric

**Acceptance criteria:**
- Every metric in `06_EVAL_SPEC.md` §3–§6 implemented
- Every §9 fixture passes at 1e-6 tolerance
- Bootstrap CI works on lists and numpy arrays; deterministic with seed
- Quality gate refuses invalid benchmark entries
- `make eval` produces a complete report

**Checkpoint:**
```bash
make eval && pytest tests/test_metrics.py tests/test_stats.py tests/test_benchmark_gate.py -v
```

---

## Phase 8 — Dashboard 🟢

**Goal:** Streamlit dashboard with 4 views.

**Deliverables:**
```
src/compliance_runtime/dashboard/__init__.py
src/compliance_runtime/dashboard/app.py
src/compliance_runtime/dashboard/state.py
src/compliance_runtime/dashboard/theme.py
src/compliance_runtime/dashboard/views/__init__.py
src/compliance_runtime/dashboard/views/live_actions.py
src/compliance_runtime/dashboard/views/approvals.py
src/compliance_runtime/dashboard/views/evidence_chain.py
src/compliance_runtime/dashboard/views/compliance_summary.py
src/compliance_runtime/dashboard/components/__init__.py
src/compliance_runtime/dashboard/components/disposition_badge.py
src/compliance_runtime/dashboard/components/approval_form.py
src/compliance_runtime/dashboard/components/chain_viewer.py
scripts/dashboard_selftest.py
tests/test_dashboard_views.py
```

**Prevention mechanisms active:**
- Lesson 2: `--self-test` for every view

**Security controls active:**
- C-06: HTML escape parameters in dashboard
- C-30: dashboard shows policy hash

**Acceptance criteria:**
- All 4 views render from fixture data
- Approval actions from dashboard go through `ApprovalService`
  (import-graph test)
- Parameters are HTML-escaped
- Policy hash displayed
- Renders in ≤ 2 s for 500 items

**Checkpoint:**
```bash
make serve & sleep 5 && curl -s localhost:8501 | head -20 && python scripts/dashboard_selftest.py && kill %1
```

---

## Phase 9 — Dossier generator + mock agent + demo 🟢

**Goal:** Generate PDF compliance dossier. Ship mock agent and demo
command.

**Deliverables:**
```
src/compliance_runtime/dossier/__init__.py
src/compliance_runtime/dossier/generator.py
src/compliance_runtime/dossier/ai_act_mapping.py
src/compliance_runtime/dossier/templates/dossier.html
src/compliance_runtime/mock_agent/__init__.py
src/compliance_runtime/mock_agent/agent.py
src/compliance_runtime/mock_agent/runner.py
data/demo/agent_scripts/demo_001.json
data/demo/agent_scripts/demo_002.json
data/demo/agent_scripts/demo_003.json
scripts/09_demo.py
tests/test_dossier.py
tests/test_mock_agent.py
tests/test_demo_integration.py
tests/security/test_export_safety.py        # C-38, C-39, C-40
```

**Prevention mechanisms active:**
- Lesson 3: behavior-only tests
- Lesson 5: read back generated dossier

**Security controls active:**
- C-38, C-39, C-40: dossier field whitelist, private key never in
  export, public key labeled

**Acceptance criteria:**
- `make dossier` produces a valid PDF
- Dossier includes EU AI Act Article 12 mapping
- Dossier field whitelist enforced
- Private key never appears in dossier
- Mock agent runs scripted tool calls through runtime
- `make demo` runs end-to-end in < 60 s

**Checkpoint:**
```bash
make demo && pytest tests/test_dossier.py tests/test_demo_integration.py tests/security/test_export_safety.py -v
```

---

## Phase 10 — Security hardening + Docker + CI ⚪

**Goal:** Finalize Docker, wire CI, verify all controls.

**Deliverables:**
```
Dockerfile                       # multi-stage, CPU-only torch
docker-compose.yml               # finalized
.dockerignore
.gitattributes
.github/workflows/ci.yml         # test + pip-audit + docker build
.github/pull_request_template.md
docs/security.md                 # public-facing summary
tests/security/test_dependency_pinning.py    # C-41 to C-44
```

**Security controls active:**
- C-41 to C-44: pinned deps, maintained packages, pip-audit in CI,
  lockfile-only installs in CI

**Acceptance criteria:**
- All P0 controls implemented and tested
- All P1 controls implemented
- `pip-audit` reports no high-severity vulnerabilities
- `docker compose up` starts runtime and dashboard
- CI runs tests + pip-audit + docker build
- CI is green on push

**Checkpoint:**
```bash
pytest tests/security/ -v && pip-audit && docker compose config && docker build -t cr:test .
```

---

## Phase 11 — Documentation + launch ⚪

**Goal:** Public-facing README, CONTRIBUTING, LICENSE, screenshots,
GitHub push.

**Deliverables:**
```
README.md
CONTRIBUTING.md
LICENSE                          # MIT
docs/screenshots/                # .gitkeep + placeholder
CHANGELOG.md                     # final entry
PROJECT_BIBLE.md                 # plain-English master doc
```

**Acceptance criteria:**
- README has TL;DR, architecture, quick start, security summary,
  evaluation explainer, 30-second pitch
- CHANGELOG has all 11 phase entries
- CI badge added to README
- Repo pushed to GitHub
- `PROJECT_BIBLE.md` written in plain English

**Checkpoint:**
```bash
gh run list --limit 3
```

---

## Prevention mechanism checklist (per phase)

- [ ] `make sync` runs and updates the venv (Lesson 1)
- [ ] `make doctor` reports all imports OK (Lesson 1)
- [ ] `grep FAILED|ERROR` returns empty after `make test` (Lesson 1b)
- [ ] Every new module has a `__main__` self-test (Lesson 2)
- [ ] Every new test asserts observable behavior (Lesson 3)
- [ ] Any new dataset passes its quality gate (Lesson 4)
- [ ] Any new write is read back by a test (Lesson 5)
- [ ] Any parallelizable work is parallel (Lesson 6)
- [ ] CHANGELOG updated in the same commit (Lesson 7)
- [ ] No new config sources outside `config/loader.py` (Lesson 8)
- [ ] DoD items checked with evidence (Lesson 9)
- [ ] No ADR contradictions (Lesson 10)
- [ ] `requirements.lock` regenerated via `pip-compile` (Lesson 11)
- [ ] `.gitignore` covers all runtime state (`*.db*`, `*.pem`) (Lesson 12)

**The phase-tracker agent refuses to close a phase if any box is
unchecked without a documented exception.**

## Definition of Done (project level)

- [ ] All 11 phases marked 🟢
- [ ] All success metrics in `00_DISCOVERY.md` §6 within target
- [ ] All P0 and P1 security controls implemented
- [ ] `make demo` works from a fresh clone in ≤ 60 seconds
- [ ] Test coverage ≥ 85% on core modules
- [ ] CI green; `pip-audit` clean
- [ ] README complete with real numbers
- [ ] `PROJECT_BIBLE.md` written
- [ ] Repo pushed to GitHub