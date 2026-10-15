"""Policy integrity: content hash + refuse-to-start (C-28, C-29, C-31)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from compliance_runtime.exceptions import PolicyLoadError, PolicyValidationError
from compliance_runtime.policy.engine import PolicyEngine
from compliance_runtime.policy.loader import load_policy_set
from compliance_runtime.policy.models import (
    Policy,
    PolicyEnforcement,
    PolicyRule,
    PolicySet,
)
from compliance_runtime.storage.models import ToolCall
from compliance_runtime.utils.ids import new_ulid, now_utc

_POLICY_DIR = Path("configs/policies")


def test_policy_set_content_hash_stable() -> None:
    assert (
        load_policy_set(_POLICY_DIR).content_hash
        == load_policy_set(_POLICY_DIR).content_hash
    )


def test_policy_set_content_hash_changes_on_edit(tmp_path: Path) -> None:
    shutil.copy(_POLICY_DIR / "demo_policy.yaml", tmp_path / "demo_policy.yaml")
    original = load_policy_set(tmp_path).content_hash

    text = (tmp_path / "demo_policy.yaml").read_text(encoding="utf-8")
    (tmp_path / "demo_policy.yaml").write_text(
        text.replace("value: 500", "value: 999"), encoding="utf-8"
    )
    assert load_policy_set(tmp_path).content_hash != original


def test_evaluation_records_content_hash() -> None:
    ps = load_policy_set(_POLICY_DIR)
    engine = PolicyEngine(ps)
    call = ToolCall(
        call_id=new_ulid(),
        correlation_id=new_ulid(),
        agent_id="a",
        session_id="s",
        action="issue_refund",
        parameters={"amount": 100},
        received_at=now_utc(),
    )
    result = engine.evaluate(call)
    # The content hash is embedded in the recorded policy_version (C-29).
    assert ps.content_hash[:8] in result.policy_version


def test_engine_refuses_to_start_with_invalid_policy(tmp_path: Path) -> None:
    (tmp_path / "broken.yaml").write_text(
        "name: broken\nversion: '1.0.0'\n", encoding="utf-8"  # missing rules
    )
    with pytest.raises(PolicyLoadError):
        PolicyEngine(load_policy_set(tmp_path))


def test_engine_does_not_start_with_empty_policy_set(tmp_path: Path) -> None:
    # An empty directory has no policies to load.
    with pytest.raises(PolicyLoadError):
        PolicyEngine(load_policy_set(tmp_path))


# --- Semantic validation is enforced on the load path (C-31) -------------


def test_load_policy_set_rejects_empty_when(tmp_path: Path) -> None:
    (tmp_path / "p.yaml").write_text(
        "name: bad\nversion: '1.0'\nrules:\n"
        "  - id: r1\n    priority: 10\n    description: x\n"
        "    when: []\n    enforce:\n      disposition: allow\n      reason: ok\n",
        encoding="utf-8",
    )
    with pytest.raises(PolicyValidationError):
        load_policy_set(tmp_path)


def test_load_policy_set_rejects_duplicate_priorities(tmp_path: Path) -> None:
    (tmp_path / "p.yaml").write_text(
        "name: bad\nversion: '1.0'\nrules:\n"
        "  - id: r1\n    priority: 10\n    description: x\n"
        "    when:\n      - field: action\n        operator: equals\n"
        "        value: a\n    enforce:\n      disposition: allow\n      reason: ok\n"
        "  - id: r2\n    priority: 10\n    description: y\n"
        "    when:\n      - field: action\n        operator: equals\n"
        "        value: b\n    enforce:\n      disposition: deny\n"
        "      reason: denied\n",
        encoding="utf-8",
    )
    with pytest.raises(PolicyValidationError):
        load_policy_set(tmp_path)


def test_load_policy_set_rejects_invalid_field_pattern(tmp_path: Path) -> None:
    (tmp_path / "p.yaml").write_text(
        "name: bad\nversion: '1.0'\nrules:\n"
        "  - id: r1\n    priority: 10\n    description: x\n"
        "    when:\n      - field: foo.bar.baz.qux\n        operator: equals\n"
        "        value: 1\n    enforce:\n      disposition: allow\n      reason: ok\n",
        encoding="utf-8",
    )
    with pytest.raises(PolicyValidationError):
        load_policy_set(tmp_path)


def test_load_policy_set_rejects_missing_require_role(tmp_path: Path) -> None:
    (tmp_path / "p.yaml").write_text(
        "name: bad\nversion: '1.0'\nrules:\n"
        "  - id: r1\n    priority: 10\n    description: x\n"
        "    when:\n      - field: action\n        operator: equals\n"
        "        value: a\n    enforce:\n"
        "      disposition: require_approval\n      reason: needs sign-off\n",
        encoding="utf-8",
    )
    with pytest.raises(PolicyValidationError):
        load_policy_set(tmp_path)


def test_engine_construction_rejects_unvalidated_policy() -> None:
    # Build a PolicySet manually (bypassing load_policy_set) with a rule
    # whose 'when' is empty — the engine must still refuse to start.
    bad_rule = PolicyRule.model_construct(
        id="r1",
        priority=10,
        description="x",
        when=[],
        enforce=PolicyEnforcement(disposition="allow", reason="ok"),
    )
    policy = Policy.model_construct(name="bad", version="1.0", rules=[bad_rule])
    ps = PolicySet.model_construct(
        policies=[policy], version="bad@1.0+0", content_hash="0" * 64
    )
    with pytest.raises(PolicyValidationError):
        PolicyEngine(ps)
