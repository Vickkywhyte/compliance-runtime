# Changelog

Newest-first order.

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
