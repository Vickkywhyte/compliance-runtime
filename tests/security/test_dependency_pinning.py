"""Dependency-hygiene tests (C-41 to C-44, Lesson 11).

Static checks only — no network, no pip-compile shell-outs. They assert the
lockfile pins exact versions with no local paths, that pyproject declares the
runtime deps, that lock and pyproject do not drift, and that CI is wired.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_LOCK = Path("requirements.lock")
_PYPROJECT = Path("pyproject.toml")
_CI = Path(".github/workflows/ci.yml")

# Import-time runtime dependencies that must be declared (heuristic subset).
_EXPECTED_DEPS = [
    "pydantic", "structlog", "cryptography", "reportlab", "fastapi",
    "uvicorn", "streamlit", "plotly", "pyyaml", "ulid", "python-dotenv",
]


def _lock_requirement_lines() -> list[str]:
    """Return the ``name==version`` requirement lines (comments stripped)."""
    lines: list[str] = []
    for raw in _LOCK.read_text(encoding="utf-8").splitlines():
        text = raw.split("#", 1)[0].strip()
        if text:
            lines.append(text)
    return lines


def _pyproject_dep_names() -> list[str]:
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    names = []
    for dep in data["project"]["dependencies"]:
        name = re.split(r"[<>=!~\[ ]", dep, 1)[0]
        names.append(name.strip().lower().replace("_", "-"))
    return names


def test_requirements_lock_exists() -> None:
    assert _LOCK.exists()


def test_requirements_lock_pins_exact_versions() -> None:
    pattern = re.compile(r"^[A-Za-z0-9._-]+==[0-9][A-Za-z0-9._+!-]*$")
    for line in _lock_requirement_lines():
        assert pattern.match(line), f"not an exact pin: {line!r}"


def test_requirements_lock_has_no_local_paths() -> None:
    text = _LOCK.read_text(encoding="utf-8")
    for marker in ("/Users/", "/home/", "file://"):
        assert marker not in text, f"lockfile contains local path marker {marker!r}"


def test_pyproject_declares_all_runtime_deps() -> None:
    deps_blob = "\n".join(
        tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
        ["project"]["dependencies"]
    ).lower()
    for name in _EXPECTED_DEPS:
        assert name in deps_blob, f"{name} not declared in pyproject dependencies"


def test_no_lockfile_drift() -> None:
    lock = _LOCK.read_text(encoding="utf-8").lower()
    for name in _pyproject_dep_names():
        assert re.search(rf"(?m)^{re.escape(name)}==", lock), (
            f"{name} declared in pyproject but absent from requirements.lock"
        )


def test_ci_workflow_exists() -> None:
    assert _CI.exists()


def test_ci_workflow_has_docker_build() -> None:
    assert "docker build" in _CI.read_text(encoding="utf-8")
