#!/usr/bin/env python
"""Pre-commit hook: enforce CHANGELOG updates in the same commit (Lesson 7).

Fails if any staged file under ``src/`` or ``scripts/`` is being committed
without ``CHANGELOG.md`` also staged in the same commit. Pre-commit passes
the staged filenames as arguments.
"""

from __future__ import annotations

import subprocess
import sys


def _staged_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def main(argv: list[str]) -> int:
    files = argv or _staged_files()
    touches_code = any(
        f.startswith("src/") or f.startswith("scripts/") for f in files
    )
    if not touches_code:
        return 0
    if any(f == "CHANGELOG.md" for f in files):
        return 0

    print(
        "CHANGELOG.md must be updated in the same commit as changes to "
        "src/ or scripts/ (Lesson 7).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
