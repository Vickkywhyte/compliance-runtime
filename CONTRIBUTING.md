# Contributing

Thanks for your interest in the AI Compliance Runtime. This project is
security-critical and evaluation-first; the contribution workflow reflects that.

## Development setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
make doctor        # verify every module imports
make test          # run the full suite
```

The project targets **Python 3.11**. Dependencies are pinned in
`requirements.lock` (generated with `pip-compile`, never `pip freeze`); update
it with `make lock` after any change to `pyproject.toml`.

## Ground rules (from `claude_chat/CLAUDE.md`)

- **Type hints on every function;** `from __future__ import annotations`.
- **Pydantic v2** for all cross-module data.
- **No `os.getenv` outside `config/loader.py`.**
- **No raw SQL outside `storage/`;** parameterized queries only.
- **No `eval` / `exec` / `shell=True`.**
- **Every state transition writes an `AuditEvent` in the same transaction.**
- **No `print()` in application code** (self-tests and scripts may print).
- **Typed exceptions** from `exceptions.py`; no bare `except:`.
- **Never weaken a P0 security control** or contradict a locked ADR. If you
  believe one should change, propose a new ADR and wait for approval.

## Locked decisions

Technology and design decisions are captured as ADRs in
`claude_chat/04_TECH_DECISIONS.md`. Notably: SQLite with append-only triggers
(ADR-003), SHA-256 chain + Ed25519 signatures (ADR-004), four dispositions
(ADR-006), approval with optimistic locking + TTL (ADR-007), **no LLM in the
critical path** (ADR-013), and one key pair per instance (ADR-017). Do not
contradict these without a superseding ADR.

## Tests

- Every new module has an `if __name__ == "__main__"` self-test
  (`make selftest` runs them all).
- Every write has a read-back test; tests assert observable behavior, not that
  a function was called.
- Security-sensitive behavior lives under `tests/security/` and runs on every
  PR.
- Before opening a PR:

```bash
make sync && make doctor && make test
pytest tests/ -v 2>&1 | grep -E "FAILED|ERROR"   # must be empty
pytest tests/security/ -v
make compose-config
```

## Pull requests

CI runs three jobs on every PR: **test** (pytest from the lockfile),
**security-audit** (`pip-audit --strict`), and **docker-build** (build the
image and smoke-test it). The PR template includes a security checklist derived
from `claude_chat/07_SECURITY_MODEL.md` §7 — fill it in honestly.

Update `CHANGELOG.md` in the same commit as any change to `src/` or `scripts/`
(a pre-commit hook enforces this), and update the relevant spec
(`05_DATA_SPEC.md` / `06_EVAL_SPEC.md` / `07_SECURITY_MODEL.md`) if behavior
changed.

## Reporting security issues

Please report suspected vulnerabilities privately to the maintainer rather than
opening a public issue, and allow reasonable time for a fix before disclosure.
See [`docs/security.md`](docs/security.md).
