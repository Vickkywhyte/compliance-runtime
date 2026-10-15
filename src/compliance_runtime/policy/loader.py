"""Policy loading from YAML (C-28, C-29, C-31).

- :func:`load_policy` reads and validates one policy file.
- :func:`load_policy_set` loads every ``*.yaml`` in a directory, computes a
  deterministic content hash and a combined version string, and refuses to
  return a set if any file is invalid (C-31).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml
from pydantic import ValidationError

from compliance_runtime.exceptions import PolicyLoadError
from compliance_runtime.policy.models import Policy, PolicySet
from compliance_runtime.policy.validators import validate_policy
from compliance_runtime.utils.ids import canonical_json
from compliance_runtime.utils.logging import get_logger

_logger = get_logger("policy.loader")


def load_policy(path: Path) -> Policy:
    """Load and validate a single policy YAML file."""
    if not path.exists():
        raise PolicyLoadError(f"Policy file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PolicyLoadError(f"Malformed policy YAML {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise PolicyLoadError(f"Policy root must be a mapping: {path}")
    try:
        return Policy.model_validate(raw)
    except ValidationError as exc:
        raise PolicyLoadError(f"Invalid policy {path}: {exc}") from exc


def _content_hash(policies: list[Policy]) -> str:
    """Return a deterministic sha256 over all policies (order-independent)."""
    ordered = sorted(policies, key=lambda p: p.name)
    payload = {"policies": [p.model_dump() for p in ordered]}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _combined_version(policies: list[Policy], content_hash: str) -> str:
    """Return ``name@version+name@version...+<hash8>`` (C-29)."""
    names = "+".join(
        f"{p.name}@{p.version}" for p in sorted(policies, key=lambda p: p.name)
    )
    return f"{names}+{content_hash[:8]}"


def load_policy_set(directory: Path) -> PolicySet:
    """Load all ``*.yaml`` policies in ``directory`` into a PolicySet.

    Each policy is validated both structurally (Pydantic, raising
    :class:`PolicyLoadError`) and semantically (:func:`validate_policy`,
    raising :class:`~compliance_runtime.exceptions.PolicyValidationError`).
    Either failure prevents the set from loading, so the runtime refuses to
    start on any policy error (C-31). Also raises :class:`PolicyLoadError`
    if the directory is missing or empty.
    """
    if not directory.is_dir():
        raise PolicyLoadError(f"Policy directory not found: {directory}")

    paths = sorted(directory.glob("*.yaml"))
    if not paths:
        raise PolicyLoadError(f"No policy files found in {directory}")

    policies = [load_policy(path) for path in paths]
    # Semantic validation (C-31) — propagates PolicyValidationError.
    for policy in policies:
        validate_policy(policy)
    content_hash = _content_hash(policies)
    version = _combined_version(policies, content_hash)

    _logger.info(
        "policy_set_loaded",
        n_policies=len(policies),
        n_rules=sum(len(p.rules) for p in policies),
        version=version,
        content_hash=content_hash,
    )
    return PolicySet(policies=policies, version=version, content_hash=content_hash)


def _self_test() -> None:
    """Load the shipped demo policy set and confirm a stable hash."""
    ps = load_policy_set(Path("configs/policies"))
    assert ps.policies, "no policies loaded"
    assert len(ps.content_hash) == 64
    again = load_policy_set(Path("configs/policies"))
    assert again.content_hash == ps.content_hash, "content hash not stable"
    print("policy.loader self-test: PASS")


if __name__ == "__main__":
    _self_test()
