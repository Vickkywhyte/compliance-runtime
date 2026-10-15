#!/usr/bin/env python
"""Module self-test runner (Lesson 2).

Discovers every module under ``src/compliance_runtime`` that has an
``if __name__ == "__main__"`` block and runs it via
``python -m compliance_runtime.<module>``. Reports pass/fail per module and
exits non-zero if any fails.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parent.parent / "src"
_PKG_ROOT = _SRC_ROOT / "compliance_runtime"
_MARKER = '__name__ == "__main__"'


def _module_name(path: Path) -> str:
    rel = path.relative_to(_SRC_ROOT).with_suffix("")
    return ".".join(rel.parts)


def discover() -> list[str]:
    """Return dotted names of modules that define a ``__main__`` block."""
    modules: list[str] = []
    for path in sorted(_PKG_ROOT.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        if _MARKER in path.read_text(encoding="utf-8"):
            modules.append(_module_name(path))
    return modules


def main() -> int:
    modules = discover()
    if not modules:
        print("selftest: no modules with a __main__ block found")
        return 1

    failures: list[str] = []
    for name in modules:
        result = subprocess.run(
            [sys.executable, "-m", name],
            capture_output=True,
            text=True,
        )
        status = "PASS" if result.returncode == 0 else "FAIL"
        print(f"  {status}  {name}")
        if result.returncode != 0:
            failures.append(name)
            if result.stdout.strip():
                print("    stdout:", result.stdout.strip().splitlines()[-1])
            if result.stderr.strip():
                print("    stderr:", result.stderr.strip().splitlines()[-1])

    print()
    if failures:
        print(f"selftest: {len(failures)}/{len(modules)} module(s) failed")
        return 1
    print(f"selftest: all {len(modules)} module self-tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
