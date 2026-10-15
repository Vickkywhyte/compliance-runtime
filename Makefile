# Makefile — AI Compliance Runtime
# Checkpoint (Phase 1): make sync && make doctor && make test && make selftest

.DEFAULT_GOAL := help
PYTHON ?= python

.PHONY: help sync doctor test selftest lock \
        clean clean-cache clean-data \
        migrate 02-migrate-selftest policy-validate 03-policy-selftest \
        eval demo serve dossier verify

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "} {printf "  %-16s %s\n", $$1, $$2}'

# --- Phase 1 targets -----------------------------------------------------

sync: ## Install the package with dev extras (Lesson 1)
	$(PYTHON) -m pip install --upgrade -e ".[dev]"

doctor: ## Import every public module and report failures (Lesson 1)
	$(PYTHON) scripts/doctor.py

test: ## Run the test suite, excluding LLM-marked tests
	$(PYTHON) -m pytest tests/ -q -m "not llm"

selftest: ## Run every module's __main__ self-test (Lesson 2)
	$(PYTHON) scripts/selftest.py

lock: ## Regenerate requirements.lock from pyproject (pip-compile, Lesson 11)
	pip-compile pyproject.toml --output-file=requirements.lock \
		--strip-extras --resolver=backtracking

# --- Cleaning ------------------------------------------------------------

clean: clean-cache ## Remove caches and build artifacts
	rm -rf build dist *.egg-info src/*.egg-info

clean-cache: ## Remove Python / tool caches
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov

clean-data: ## Remove the local SQLite database and logs (DESTRUCTIVE)
	rm -f data/runtime.db data/runtime.db-shm data/runtime.db-wal \
		data/runtime.db-journal
	rm -rf logs

# --- Future-phase stubs (fail until implemented) -------------------------

migrate: ## Apply storage migrations (Phase 2)
	$(PYTHON) -m compliance_runtime.storage.migrate

02-migrate-selftest: ## Phase 2 migration + round-trip self-test
	$(PYTHON) scripts/02_migrate_selftest.py

policy-validate: ## Validate every policy file (Phase 3)
	$(PYTHON) -c "from pathlib import Path; from compliance_runtime.policy.loader import load_policy_set; from compliance_runtime.policy.validators import validate_policy; ps = load_policy_set(Path('configs/policies')); [validate_policy(p) for p in ps.policies]; print(f'policy-validate OK: {len(ps.policies)} policies, {sum(len(p.rules) for p in ps.policies)} rules')"

03-policy-selftest: ## Phase 3 policy engine self-test
	$(PYTHON) scripts/03_policy_selftest.py

eval: ## (stub) run the evaluation harness — Phase 7
	@echo "eval: not implemented yet (Phase 7)" >&2; exit 1

demo: ## (stub) run the end-to-end demo — Phase 9
	@echo "demo: not implemented yet (Phase 9)" >&2; exit 1

serve: ## (stub) start the runtime + dashboard — Phase 6/8
	@echo "serve: not implemented yet (Phase 6/8)" >&2; exit 1

dossier: ## (stub) generate a compliance dossier — Phase 9
	@echo "dossier: not implemented yet (Phase 9)" >&2; exit 1

verify: ## (stub) verify the evidence chain — Phase 4
	@echo "verify: not implemented yet (Phase 4)" >&2; exit 1
