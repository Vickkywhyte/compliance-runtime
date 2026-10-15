"""Tests for policy loading (C-28, C-29, C-31)."""

from __future__ import annotations

from pathlib import Path

import pytest

from compliance_runtime.exceptions import PolicyLoadError
from compliance_runtime.policy.loader import load_policy, load_policy_set

_POLICY_DIR = Path("configs/policies")
_DEMO = _POLICY_DIR / "demo_policy.yaml"


def test_load_valid_policy() -> None:
    policy = load_policy(_DEMO)
    assert policy.name == "demo_policy"
    assert len(policy.rules) == 3


def test_load_missing_file_raises() -> None:
    with pytest.raises(PolicyLoadError):
        load_policy(Path("configs/policies/does_not_exist.yaml"))


def test_load_malformed_yaml_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("name: [unterminated\n", encoding="utf-8")
    with pytest.raises(PolicyLoadError):
        load_policy(bad)


def test_load_policy_set_computes_hash() -> None:
    ps = load_policy_set(_POLICY_DIR)
    assert len(ps.content_hash) == 64
    assert ps.content_hash == load_policy_set(_POLICY_DIR).content_hash


def test_load_policy_set_computes_version() -> None:
    ps = load_policy_set(_POLICY_DIR)
    assert ps.version.startswith("demo_policy@1.0.0+")
    assert ps.content_hash[:8] in ps.version


def test_load_policy_set_rejects_invalid(tmp_path: Path) -> None:
    # A structurally invalid policy (missing required 'rules') must fail.
    (tmp_path / "broken.yaml").write_text(
        "name: broken\nversion: '1.0.0'\n", encoding="utf-8"
    )
    with pytest.raises(PolicyLoadError):
        load_policy_set(tmp_path)
