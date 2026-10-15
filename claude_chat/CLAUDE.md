# CLAUDE.md — Operating Rules for Claude Code

> **READ THIS FILE COMPLETELY before making any change to this repository.**
> It is the operating manual for AI-assisted work on the AI Compliance
> Runtime. It supersedes any default behavior.
>
> **Precedence order (highest to lowest):**
> 1. This file
> 2. `04_TECH_DECISIONS.md` (locked ADRs)
> 3. `07_SECURITY_MODEL.md` (P0 controls)
> 4. `06_EVAL_SPEC.md` (metric definitions)
> 5. Everything else
>
> If two sources conflict, the higher-precedence source wins. Flag the
> conflict. Do not resolve it silently.

---

## 1. Project in one paragraph

An open-source runtime that intercepts AI agent tool calls, enforces
policy in real time, requires human approval for high-stakes actions,
and produces cryptographically-verifiable evidence for regulators.
Works with any agent using OpenAI-compatible function calling. Costs
$0 to run.

**The pitch:** *"AI agents are being deployed to take real actions
inside enterprises. Almost nobody can prove what those agents were
authorized to do, what they actually did, or how the two were enforced.
I built the open-source runtime that closes that gap."*

## 2. Required reading before any non-trivial change

Read in this order:

1. `CLAUDE.md` (this file)
2. `00_DISCOVERY.md` — problem, scope, success metrics
3. `01_LESSONS_APPLIED.md` — 12 prevention mechanisms (mandatory)
4. `02_PRD.md` — functional requirements
5. `03_ARCHITECTURE.md` — component design
6. `04_TECH_DECISIONS.md` — 18 locked ADRs
7. `05_DATA_SPEC.md` — every schema
8. `06_EVAL_SPEC.md` — every metric
9. `07_SECURITY_MODEL.md` — threat model + P0/P1 controls
10. `08_ROADMAP.md` — current phase and its deliverables
11. `09_RUNTIME_DESIGN.md` — how the runtime reasons and enforces

**Never contradict a locked ADR.** If you believe one should change,
propose a new ADR (e.g., ADR-019) and wait for approval.

**Never weaken a P0 security control.** Flag it and wait.

**The runtime is a high-value target.** Any change that could allow a
policy bypass, evidence tampering, or approval bypass requires
exceptional scrutiny.

## 3. Repository layout (quick reference)

```
compliance-runtime/
├── claude_chat/                    # ALL planning docs (this file's home)
├── configs/
│   ├── runtime.yaml
│   ├── eval.yaml
│   └── policies/                   # YAML policy files
├── data/
│   ├── runtime.db                  # SQLite (gitignored)
│   ├── eval/                       # benchmark dataset (committed)
│   ├── demo/                       # mock agent scripts (committed)
│   └── *.db-shm, *.db-wal          # SQLite sidecars (gitignored)
├── logs/                           # app.jsonl (gitignored)
├── results/
│   ├── evals/                      # eval reports (gitignored)
│   └── dossiers/                   # generated PDFs (gitignored)
├── src/compliance_runtime/         # library code (see 03_ARCHITECTURE §6)
├── scripts/                        # numbered runnable entry points
├── tests/                          # mirrors src/
│   └── security/                   # security tests (mandatory)
├── notebooks/                      # exploration only
├── pyproject.toml
├── requirements.lock               # via pip-compile, not pip freeze
├── Makefile
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── .gitattributes
└── .github/workflows/ci.yml
```

## 4. Phase discipline

Work on exactly one phase at a time, in order, from `08_ROADMAP.md`.
The current phase is stated at the top of the user's message. If
unstated, **ask before proceeding.**

Do not pre-build future phases. Do not volunteer future-phase work.

**At the start of every phase:**
1. Read the phase's deliverables in `08_ROADMAP.md`
2. Read the prevention-mechanism checklist at the end of `08_ROADMAP.md`
3. Confirm the checkpoint command

**At the end of every phase:**
1. Run `make sync && make doctor` (Lesson 1)
2. Run `pytest tests/ -v 2>&1 | grep -E "FAILED|ERROR"` and confirm empty (Lesson 1b)
3. Run every new module's `__main__` self-test (Lesson 2)
4. Run the phase's checkpoint command
5. Run `make test`
6. Update `CHANGELOG.md` in the SAME commit as the code (Lesson 7)
7. Invoke the `phase-tracker` agent
8. Only then declare the phase complete

## 5. Coding rules

1. **Type hints on every function.** `from __future__ import annotations`.
2. **ABCs before implementations.** New policy operator, disposition
   handler, metric → inherit from base and register.
3. **Pydantic v2** for all cross-module data. See `05_DATA_SPEC.md`.
4. **No direct crypto calls outside `evidence/signing.py`.** The private
   key lives only there.
5. **No direct `os.getenv` outside `config/loader.py`** (Lesson 8).
6. **No raw SQL outside `storage/`.** Parameterized queries only.
7. **No `eval`, `exec`, or `shell=True`.** (C-11)
8. **Every state transition writes an `AuditEvent`** in the same
   transaction (C-23).
9. **Config over constants.** No magic numbers. Thresholds and TTLs →
   YAML (Lesson 8).
10. **Determinism.** Same input → same output. No `datetime.now()` in
    the hashed fields — timestamps come from the caller.
11. **Fail loud in dev, fail soft in prod.** Config/policy errors
    refuse to start. Per-action errors return a `deny` disposition and
    are logged.
12. **No `print()`.** Use `structlog`. Exception: `__main__` self-tests
    may `print()` for readable output.
13. **Docstrings** on every module and class.
14. **Typed exceptions** from `exceptions.py`. No bare `except:`.

## 6. Do NOT

- ❌ Do not install packages without updating `pyproject.toml` AND
  running `make sync`
- ❌ Do not call real LLMs anywhere in the runtime (ADR-013)
- ❌ Do not modify `data/eval/benchmark.jsonl` programmatically
- ❌ Do not add a metric without updating `06_EVAL_SPEC.md` + a test
- ❌ Do not use `print()` in application code
- ❌ Do not add files outside the current phase's deliverable list
- ❌ Do not refactor previous phases' code while in the current phase
- ❌ Do not silently change an ADR — propose a new one
- ❌ Do not weaken a P0 security control
- ❌ Do not bypass human-in-the-loop for any reason, ever
- ❌ Do not let the runtime execute a tool (it only authorizes)
- ❌ Do not log a private key (C-15); the scrubber catches this, but
  don't try
- ❌ Do not use `pip freeze` to generate `requirements.lock` — use
  `pip-compile`
- ❌ Do not commit `*.db`, `*.db-shm`, `*.db-wal`, `*.db-journal`, or
  `*.pem`
- ❌ Do not modify anything in `claude_chat/` unless the user explicitly
  asks

## 7. Prevention mechanisms (from `01_LESSONS_APPLIED.md`)

| # | Mechanism | Enforced by |
|---|---|---|
| 1 | `make sync` + `make doctor` before every checkpoint | Every phase |
| 1b | `grep FAILED\|ERROR` after every test run | Every phase |
| 2 | `--self-test` on every runnable | Every script/module |
| 3 | Tests assert observable behavior | Every test |
| 4 | Quality gate runs during curation | Benchmark dataset |
| 5 | Every write has a read-back test | Every persistence layer |
| 6 | Concurrency in architecture | Rate limiter, evidence writer |
| 7 | CHANGELOG updates in same commit | Pre-commit hook |
| 8 | One config per concern; `os.getenv` only in `config/loader.py` | Lint rule + review |
| 9 | DoD checked with evidence | phase-tracker agent |
| 10 | ADRs locked before build | This file + ADRs |
| 11 | `pip-compile`, not `pip freeze` | CI check + review |
| 12 | `.gitignore` covers all runtime state | CI check + review |

## 8. Checkpoint commands

| Phase | Command |
|---|---|
| 1 | `make sync && make doctor && make test && make selftest` |
| 2 | `make migrate && pytest tests/test_storage.py tests/test_repositories.py -v` |
| 3 | `make policy-validate && pytest tests/test_policy_engine.py tests/security/test_policy_bypass.py -v` |
| 4 | `python scripts/04_evidence_selftest.py && pytest tests/test_recorder.py tests/test_verifier.py tests/security/test_key_safety.py -v` |
| 5 | `python scripts/05_approval_selftest.py && pytest tests/security/test_approval_integrity.py -v` |
| 6 | `python scripts/06_runtime_selftest.py && pytest tests/test_server.py tests/test_sdk.py -v` |
| 7 | `make eval && pytest tests/test_metrics.py tests/test_stats.py tests/test_benchmark_gate.py -v` |
| 8 | `make serve & sleep 5 && python scripts/dashboard_selftest.py && kill %1` |
| 9 | `make demo && pytest tests/test_dossier.py tests/test_demo_integration.py tests/security/test_export_safety.py -v` |
| 10 | `pytest tests/security/ -v && pip-audit && docker compose config && docker build -t cr:test .` |
| 11 | `gh run list --limit 3` |

**If a checkpoint fails, do not proceed.**

## 9. Commit message format

`[phase-N] type(scope): summary`

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `eval`, `sec`

Examples:
```
[phase-3] feat(policy): priority-ordered evaluation with four dispositions
[phase-4] sec(evidence): add Ed25519 signatures to hash chain
[phase-5] fix(approvals): prevent double-approval with optimistic lock
[phase-7] eval(metrics): implement policy precision with fixtures
```

**Every commit that changes `src/` or `scripts/` must also update
`CHANGELOG.md`.** The pre-commit hook enforces this.

## 10. Response style (for AI assistant)

- **Concise and technical.** No filler.
- **Show, don't tell.** Full code blocks, exact paths, real commands.
- **Flag uncertainty explicitly.** Propose how to verify.
- **Surface trade-offs** in one sentence when a choice is non-obvious.
- **Respect "one step at a time."** Do not volunteer future phases.
- **Never claim "done" without evidence.** Paste the exact command and
  its output.

## 11. When to ask vs. proceed

**Ask before proceeding if:**
- The change touches metric definitions (`06_EVAL_SPEC.md`)
- The change contradicts an ADR
- The change weakens a P0 security control
- The phase is ambiguous
- A crypto library behavior is uncertain and affects correctness
- A change could affect the evidence chain's integrity

**Proceed without asking if:**
- Clear deliverable within the current phase
- Follows an established pattern from a previous phase
- Bug fix with obvious correct behavior
- Formatting, docstrings, or type hints

## 12. The phase-tracker agent

Located at `.claude/agents/phase-tracker.md`.

**Invoke at the close of every phase.**

**What it does:**
1. Verifies every deliverable exists
2. Verifies every prevention-mechanism checkbox has evidence
3. Updates `08_ROADMAP.md` (phase → 🟢)
4. Updates `00_START_HERE.md` (status table)
5. Updates `CHANGELOG.md` with a completed entry
6. Refuses to close if any DoD item lacks evidence

**The phase is not complete until the agent has run and succeeded.**

## 13. Session hygiene

Before ending any session:

- [ ] `CHANGELOG.md` updated (if a phase moved)
- [ ] Phase status updated in `08_ROADMAP.md` and `00_START_HERE.md`
- [ ] Any new decision captured as an ADR
- [ ] Any new metric added to `06_EVAL_SPEC.md` with test reference
- [ ] No `TODO` comments left in committed files
- [ ] `make test` passes
- [ ] `grep FAILED|ERROR` returns empty
- [ ] No `.env` file staged or committed
- [ ] No `*.pem` file staged or committed
- [ ] No `*.db*` sidecar files staged or committed

## 14. When stuck

Ask. Do not guess.

- **Uncertain about a metric?** Read `06_EVAL_SPEC.md` and ask.
- **Uncertain about a schema?** Read `05_DATA_SPEC.md` and ask.
- **Uncertain about a security control?** Read `07_SECURITY_MODEL.md`
  and ask.
- **Uncertain about the crypto layer?** Read
  `09_RUNTIME_DESIGN.md` §7 and ask.
- **Uncertain about phase scope?** Read `08_ROADMAP.md` and ask.

**A wrong guess in the crypto layer can silently break evidence
integrity. Ask.**