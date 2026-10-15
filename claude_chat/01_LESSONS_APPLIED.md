# Lessons Applied — AI Compliance Runtime

> **READ THIS FIRST (for Claude Code):**
> This is a prevention checklist. Every failure from the prior two
> projects has an explicit mechanism here. When making any build
> decision, treat this as a constraint, not a suggestion. If a proposed
> approach contradicts a prevention mechanism, stop and flag it.
>
> Referenced by `04_TECH_DECISIONS.md` and `CLAUDE.md`.

---

## Why this document exists

Two projects have shipped before this one:

- **Document Intelligence Platform** — RAG with first-class evaluation
- **Compliance Monitoring Agent** — regulatory change monitoring with
  39 security controls

Both succeeded. Both also hit preventable friction that cost hours. This
document ensures none of it recurs.

Each lesson is: **(a)** what went wrong, **(b)** the concrete cost,
**(c)** the mechanism that prevents it.

---

## Lesson 1 — Dependency drift

**What went wrong.** `pyproject.toml` was edited to add new dependencies,
but the active venv was never updated. Missing imports surfaced only at
phase checkpoints. Happened with `unstructured`, `tiktoken`, `chromadb`,
`openai`, `plotly`, `kaleido`, `fastapi`, `streamlit`, and more.

**Cost.** ~90 minutes across both projects, spread over 12 incidents.

**Prevention.**
- `make sync` runs `pip install --upgrade -e ".[dev]"` from Phase 1
- `make doctor` imports every public module and reports missing deps
- Every phase checkpoint begins with `make sync && make doctor`
- `CLAUDE.md` requires `make sync` + `make doctor` after any
  `pyproject.toml` change

## Lesson 1b — "Passing" means "ran and passed"

**What went wrong.** Phase 6 verification of the compliance monitoring
agent reported "10 tests passed." Four of those tests were failing at
import time (plotly declared in `pyproject.toml` but never installed).
The tests were collecting but crashing at import.

**Cost.** ~45 minutes in Phase 8 when the truth was discovered.

**Prevention.**
- Every phase verification runs
  `pytest tests/ -v 2>&1 | grep -E "FAILED|ERROR" | head -10`
- Any output from that grep is a failure, even if the summary line says
  "N passed"
- `make sync` uses `--upgrade` to force pip to re-check every declared
  dependency

## Lesson 2 — Verification at the wrong granularity

**What went wrong.** Verification happened at the phase level, so
sub-tasks were skipped. The Phase 10 incident where `app.routes` showed
only `/health` was 20 minutes of panic caused by testing at the wrong
layer (FastAPI lazy router registration).

**Cost.** ~45 minutes; one near-miss on a false alarm.

**Prevention.**
- Every runnable entry point supports a `--self-test` flag
- Every phase has `make verify-phase-N` that runs all that phase's
  self-tests
- No sub-task is marked complete until its self-test passes

## Lesson 3 — Tests that pass without testing

**What went wrong.** API tests passed even though routes weren't
registered. Some tests verified "the function was called" rather than
"the endpoint returned the right response."

**Cost.** Nearly shipped a broken API.

**Prevention.**
- Every test asserts observable behavior: return value, HTTP status,
  persisted side effect, or emitted log event
- No tests that only verify function invocation (`mock.assert_called`)
- The evaluation harness's critical path is verified by mutation
  testing: intentionally break one line, confirm a test fails

## Lesson 4 — Golden dataset quality discovered late

**What went wrong.** The RAG project's curated dataset had two problems
discovered *after* curation: 43 answers were fragmented substrings, and
18 questions were near-duplicates.

**Cost.** ~2 hours; required a rewrite pass.

**Prevention.**
- Every curated dataset has a quality gate script that runs *during*
  curation, not after
- The gate fails on: duplicates, fragments, missing fields, length
  violations, cross-reference failures
- No dataset is committed unless the gate passes

## Lesson 5 — Logging that didn't log

**What went wrong.** `logs/app.jsonl` was supposed to receive structlog
JSON events. It received only third-party plaintext. The bug existed
from Phase 1 and was discovered in Phase 11 because nothing had ever
*read back* from the file.

**Cost.** ~30 minutes; required a logging module rewrite late.

**Prevention.**
- Every write has a read-back test
- The logging subsystem has a self-test in Phase 1's checkpoint
- No blind writes anywhere in the codebase

## Lesson 6 — Serial execution where parallelism was possible

**What went wrong.** The RAG project's 6-config matrix ran 450 LLM calls
sequentially. Wall time: ~30 minutes.

**Cost.** Blocked faster iteration; acceptable for one-off runs.

**Prevention.**
- Concurrency is in the architecture, not bolted on
- Components that can run concurrently have explicit concurrency models
- Rate-limit-aware concurrency: a semaphore caps in-flight LLM requests

## Lesson 7 — CHANGELOG lag

**What went wrong.** CHANGELOG updates were often applied retroactively,
leading to less-detailed records.

**Cost.** ~1 hour of reconstruction effort across projects.

**Prevention.**
- CHANGELOG updates happen in the same commit as the code change
- Enforced by a `pre-commit` hook that fails if `CHANGELOG.md` wasn't
  touched in a commit that changed `src/` or `scripts/`
- Every phase close triggers the `phase-tracker` agent

## Lesson 8 — Ad-hoc configuration decisions

**What went wrong.** Configuration parameters were sometimes decided in
code, sometimes in YAML, sometimes in environment variables — sometimes
in all three with different values.

**Cost.** Debugging time; confusion around Phases 4 and 9.

**Prevention.**
- One config file per concern
- Every parameter loaded via a Pydantic config model
- Lint rule: `grep -r "os.getenv" src/` returns only hits inside
  `src/*/config/loader.py`

## Lesson 9 — "Done" assumed, not demonstrated

**What went wrong.** Phases were sometimes declared done based on Claude
Code's self-report. Verification occasionally revealed skipped steps.

**Cost.** Several partial re-runs; one near-miss on a broken API.

**Prevention.**
- The Definition of Done is a checklist with evidence requirements
- Every box has a specific, verifiable proof (test path, file path, log
  line, report artifact)
- No box is checked without evidence
- The phase-tracker agent refuses to mark a phase complete if any DoD
  item lacks an evidence field

## Lesson 10 — Mid-build technology debates

**What went wrong.** Late in the RAG project, there was a debate about
Streamlit vs. Next.js for the UI. This consumed half a day of decision
anxiety that could have been avoided.

**Cost.** ~4 hours of "should we or shouldn't we" that produced no
output.

**Prevention.**
- All technology decisions are made before Phase 1 and locked as ADRs
- Changing a locked decision requires a new ADR that explicitly
  supersedes the old one
- No mid-build debates

## Lesson 11 — Lockfile drift

**What went wrong.** In the compliance monitoring agent, `pyproject.toml`
was updated across multiple phases (streamlit, plotly, reportlab), but
`requirements.lock` was never regenerated. CI revealed that
`pip install -r requirements.lock` installed a stale dependency set.

**Cost.** Two CI failures; ~40 minutes of debugging.

**Prevention.**
- `requirements.lock` is regenerated with `pip-compile`, not
  `pip freeze`
- `pip-compile` reads `pyproject.toml`, so it can't drift
- The lockfile excludes dev dependencies (correct for production
  installs); CI installs dev deps separately
- CI verifies that the lockfile matches `pyproject.toml` before
  installing

## Lesson 12 — Accidental commits of runtime state

**What went wrong.** SQLite WAL sidecar files (`compliance.db-shm`,
`compliance.db-wal`) were accidentally committed. They contain recent
transactions, are machine-specific, and can corrupt a database if
restored on a different machine.

**Cost.** ~10 minutes; untrack + `.gitignore` fix.

**Prevention.**
- `.gitignore` is exhaustive: every database sidecar file is listed
- The pattern `*.db*` is included, not just `*.db`
- A CI check greps for tracked files matching `*.db-shm`, `*.db-wal`,
  or `*.db-journal` and fails if any are found

---

## Bonus lessons not in the numbered list

**B1 — Free-tier design as a feature, not a workaround.** Rate-limit-aware
design produces a system that is more portable and cost-conscious.
It is a portfolio signal, not a compromise.

**B2 — Evaluation is built first, not last.** The eval spec is written
in Stage 0 (Batch 2) before any pipeline exists. Metrics define the
interface.

**B3 — Security cannot be an afterthought.** The threat model is written
in Batch 3 and enforced from Phase 1.

**B4 — Documentation as context, not output.** Every doc opens with a
"READ THIS FIRST" block for future AI sessions.

**B5 — The runtime is a high-value target.** A compromised runtime can
authorize anything. Its security model is unusually strict.

---

## The scoreboard

| Lesson | Prevented by | Verified at |
|---|---|---|
| 1. Dependency drift | `make sync` + `make doctor` | Every phase |
| 1b. Passing means ran and passed | `grep FAILED\|ERROR` after every test run | Every phase |
| 2. Wrong verification granularity | `--self-test` + `make verify-phase-N` | Every phase |
| 3. Tests that don't test | Behavior-only assertions + mutation check | Every metric |
| 4. Late dataset quality | Quality gate during curation | Phase 7 |
| 5. Broken logging | Read-back verification | Phase 1 |
| 6. Serial execution | Concurrency in architecture | Phases 2, 4 |
| 7. CHANGELOG lag | Same-commit rule + pre-commit hook | Every commit |
| 8. Ad-hoc configuration | One config per concern + lint rule | Every phase |
| 9. Assumed done | DoD with evidence requirements | Every phase |
| 10. Mid-build debates | ADRs locked before Phase 1 | Stage 0 |
| 11. Lockfile drift | `pip-compile`, not `pip freeze` | Every dependency change |
| 12. Runtime state committed | Exhaustive `.gitignore` + CI check | Every commit |

**If any mechanism is bypassed, the bypass is itself a bug and must be
recorded in the CHANGELOG with the reason.**