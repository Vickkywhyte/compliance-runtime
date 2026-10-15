#!/usr/bin/env python
"""Environment doctor (Lesson 1).

Imports every public module in ``compliance_runtime`` and reports any that
fail (missing third-party packages are reported by name). Exits non-zero if
any import fails, so ``make doctor`` can gate a checkpoint.
"""

from __future__ import annotations

import importlib
import sys

# Every public module in the Phase 1 package surface.
MODULES = [
    "compliance_runtime",
    "compliance_runtime.exceptions",
    "compliance_runtime.config",
    "compliance_runtime.config.models",
    "compliance_runtime.config.loader",
    "compliance_runtime.config.keys",
    "compliance_runtime.utils",
    "compliance_runtime.utils.logging",
    "compliance_runtime.utils.ids",
    "compliance_runtime.storage",
    "compliance_runtime.storage.db",
    "compliance_runtime.storage.models",
    "compliance_runtime.storage.audit",
    "compliance_runtime.storage.migrations",
    "compliance_runtime.storage.migrate",
    "compliance_runtime.storage.tool_calls",
    "compliance_runtime.storage.evaluations",
    "compliance_runtime.storage.action_records",
    "compliance_runtime.storage.approvals",
    "compliance_runtime.policy",
    "compliance_runtime.policy.models",
    "compliance_runtime.policy.loader",
    "compliance_runtime.policy.validators",
    "compliance_runtime.policy.engine",
    "compliance_runtime.policy.field_resolver",
    "compliance_runtime.policy.rate_limit",
    "compliance_runtime.policy.injection",
]


def main() -> int:
    failures: list[tuple[str, str]] = []
    for name in MODULES:
        try:
            importlib.import_module(name)
            print(f"  OK    {name}")
        except Exception as exc:  # noqa: BLE001 - report any import failure
            failures.append((name, f"{type(exc).__name__}: {exc}"))
            print(f"  FAIL  {name}  ->  {type(exc).__name__}: {exc}")

    print()
    if failures:
        print(f"doctor: {len(failures)} module(s) failed to import")
        missing = sorted(
            {
                exc.split(":", 1)[1].strip().split("'")[1]
                for _, exc in failures
                if exc.startswith("ModuleNotFoundError") and "'" in exc
            }
        )
        if missing:
            print("missing packages: " + ", ".join(missing))
        return 1

    print(f"doctor: all {len(MODULES)} modules import OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
