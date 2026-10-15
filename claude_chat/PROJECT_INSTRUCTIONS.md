# Project Instructions

> **For humans.** How to work in this repository. Applies to
> contributors, reviewers, and the primary developer. AI-assisted work
> is governed by `CLAUDE.md`.

---

## 1. Mission

Build an **open-source runtime that makes AI agents defensible in
regulated environments**. Enterprises are deploying agents to take
real actions. Almost nobody can prove what those agents were
authorized to do, what they did, or how the two were enforced.

**The runtime closes that gap.** It intercepts tool calls, enforces
policy at runtime, requires human approval for high-stakes actions,
and produces cryptographically-verifiable evidence.

**The differentiator:** evaluation as a first-class concern. Enforcement
precision, recall, false positive/negative rates, evidence completeness,
chain integrity, approval latency — all measured with confidence
intervals.

**The constraint:** $0 to run.

**The bar:** a hiring manager or enterprise architect reading this repo
should conclude: *"this person understands what it takes to deploy AI in
a regulated environment."*

## 2. Working principles

Non-negotiable. Refer back here when in doubt.

### 2.1 Enforcement, not observation
Logging is not enforcement. A filter that runs after the LLM produces
output is not enforcement. Enforcement means: the runtime decides
before the action executes. The runtime is a gatekeeper, not a log.

### 2.2 Evidence must be tamper-evident
A log can be edited. A hash chain cannot — not without detection. Every
record is hash-chained and signed. Verification must be possible
offline.

### 2.3 Human-in-the-loop is the product
The runtime proposes; humans decide on high-stakes actions. This is not
a limitation — it's what makes the system deployable in regulated
environments.

### 2.4 Determinism in the critical path
No LLM in the critical path. Policy evaluation is rules-only. Same
input → same output. This makes the runtime auditable.

### 2.5 Prevention before debugging
The 12 prevention mechanisms in `01_LESSONS_APPLIED.md` are not
suggestions. They exist because we already paid for the lesson.

### 2.6 Config over code
Every parameter in YAML. `config/loader.py` is the only place
`os.getenv` lives.

### 2.7 Interfaces over implementations
Every swappable component (policy operator, disposition handler,
storage backend, metric) has an ABC.

### 2.8 Security is structural
The threat model (`07_SECURITY_MODEL.md`) is written before code. P0
controls are enforced from Phase 1. The runtime itself is a high-value
target; it is designed accordingly.

### 2.9 Phase discipline
Work one phase at a time. Do not "while I'm here, also..." Pre-building
future phases creates churn and untested code.

### 2.10 Evidence over assertion
"Done" means a command was run and its output matches the expected
result. No phase closes without evidence.

## 3. Code conventions

### Python
- **Version:** 3.11
- **Style:** PEP 8, enforced by `ruff`
- **Types:** Required on every function; `from __future__ import annotations`
- **Docstrings:** Required on every module and class
- **Imports:** Absolute (`from compliance_runtime.policy.engine import PolicyEngine`)

### Naming
| Entity | Convention | Example |
|---|---|---|
| Module | `snake_case` | `policy/engine.py` |
| Class | `PascalCase` | `PolicyEngine`, `EvidenceRecorder` |
| Function | `snake_case` | `evaluate()` |
| Constant | `UPPER_SNAKE` | `DEFAULT_TTL_SECONDS = 900` |
| Config key | `snake_case` | `default_ttl_seconds` |
| Test file | `test_{module}.py` | `test_policy_engine.py` |
| Script | `NN_verb.py` | `03_policy_selftest.py` |

### File layout
- `src/compliance_runtime/` — importable package
- `scripts/` — numbered, runnable entry points
- `configs/` — YAML only
- `tests/` — mirrors `src/` structure
- `tests/security/` — every security test
- `data/`, `logs/`, `results/` — gitignored except committed fixtures

## 4. Code review checklist

Self-review **before every commit**:

- [ ] Type hints on all public functions
- [ ] Docstring on every new module and class
- [ ] No magic numbers — pulled into config
- [ ] Errors logged with context, not swallowed
- [ ] Corresponding test added or updated
- [ ] No `print()` in application code
- [ ] No direct crypto calls outside `evidence/signing.py`
- [ ] No new `os.getenv` outside `config/loader.py`
- [ ] No raw SQL outside `storage/`
- [ ] Any state transition writes an `AuditEvent` in the same transaction
- [ ] Any new string field is escaped in logs and dashboards
- [ ] `CHANGELOG.md` updated in the same commit
- [ ] No `*.pem`, `*.db*` staged

## 5. Commit discipline

**Format:** `[phase-N] type(scope): summary`

**Types:** `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `eval`, `sec`

**Examples:**
```
[phase-3] feat(policy): priority-ordered evaluation with four dispositions
[phase-4] sec(evidence): add Ed25519 signatures to hash chain
[phase-5] fix(approvals): prevent double-approval with optimistic lock
```

**Before declaring a phase complete:**
1. All deliverables in `08_ROADMAP.md` present
2. Checkpoint command passes
3. `make test` passes; `grep FAILED|ERROR` returns empty
4. `CHANGELOG.md` updated in the same commit
5. `phase-tracker` agent run and succeeded

## 6. How to work with Claude Code

### 6.1 Point Claude at the right files first
- Always: `CLAUDE.md`
- Before coding a module: `05_DATA_SPEC.md` + the relevant ADR
- Before touching policy or dispositions: `09_RUNTIME_DESIGN.md`
- Before touching crypto: `09_RUNTIME_DESIGN.md` §7
- Before touching security: `07_SECURITY_MODEL.md`

### 6.2 One phase at a time
State the phase explicitly at the top of every session:
> *"Phase 3. Build mode."*

Do not let the assistant drift into future phases. If it offers,
decline.

### 6.3 Modes
- **Plan mode** — discuss, propose, no code
- **Build mode** — generate complete files for the current phase
- **Review mode** — critique existing code against ADRs and eval spec

### 6.4 When to push back
- If the assistant proposes a change contradicting an ADR → ask for a
  new ADR
- If the assistant proposes touching eval semantics → stop, read
  `06_EVAL_SPEC.md`, then decide
- If the assistant wants to "also refactor" something → defer to a
  dedicated phase
- If the assistant claims "done" without evidence → ask for the command
  and its output

## 7. Anti-patterns

Do NOT:

- ❌ Hardcode API keys, model names, or absolute paths
- ❌ Call real LLMs in the runtime
- ❌ Modify `data/eval/benchmark.jsonl` programmatically
- ❌ Approve without human action
- ❌ Log secrets (the scrubber catches this, but don't try)
- ❌ Add config sources outside `config/loader.py`
- ❌ Write to `action_records` outside the repository
- ❌ Let the runtime execute the underlying tool
- ❌ Add a metric without `06_EVAL_SPEC.md` + a fixture
- ❌ Use `pip freeze` for `requirements.lock`
- ❌ Commit `*.db*` or `*.pem`
- ❌ Bypass the pre-commit hooks

## 8. Testing expectations

- **Unit tests:** fast (< 1s each), no network, no LLM
- **Integration tests:** full pipeline with mock agent
- **Security tests:** in `tests/security/`, run on every PR
- **Coverage:** ≥ 85% on core modules

Every metric in `06_EVAL_SPEC.md` has a fixture in `tests/test_metrics.py`
covering both a positive and a negative case.

Every security control in `07_SECURITY_MODEL.md` §4 has a test.

## 9. Documentation discipline

- Every new decision → new ADR
- Every new metric → new section in `06_EVAL_SPEC.md` + test reference
- Every new config key → documented in `05_DATA_SPEC.md`
- Every new API endpoint → added to `02_PRD.md` §8
- Every new security control → added to `07_SECURITY_MODEL.md` §4

Documentation is not a follow-up task. It's part of "done."

## 10. Definition of "done" (per phase)

A phase is done when:

1. ✅ All deliverables in `08_ROADMAP.md` exist
2. ✅ Checkpoint command passes with expected output
3. ✅ New code has type hints + docstrings + tests
4. ✅ `CHANGELOG.md` has a dated entry (same commit)
5. ✅ No `TODO` comments left in the phase's files
6. ✅ `make sync && make doctor` passes
7. ✅ `make test` passes; `grep FAILED|ERROR` empty
8. ✅ Security checklist in `07_SECURITY_MODEL.md` §7 verified
9. ✅ `phase-tracker` agent run and succeeded
10. ✅ Status updated in `00_START_HERE.md`

**No item is checked without evidence.**

## 11. Getting help

- **Confused about a metric?** Read `06_EVAL_SPEC.md` §1
- **Confused about a schema?** Read `05_DATA_SPEC.md` §2
- **Confused about the runtime?** Read `09_RUNTIME_DESIGN.md` §2
- **Confused about security?** Read `07_SECURITY_MODEL.md` §3
- **Confused about crypto?** Read `09_RUNTIME_DESIGN.md` §7
- **Confused about the phase?** Read `08_ROADMAP.md`

Then ask. Do not guess.