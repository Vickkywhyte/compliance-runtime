"""Tests for the config loader and models (Lesson 8)."""

from __future__ import annotations

from pathlib import Path

import pytest

from compliance_runtime.config.loader import load_config
from compliance_runtime.config.models import AppConfig
from compliance_runtime.exceptions import ConfigError

_RUNTIME_YAML = "configs/runtime.yaml"


def test_config_loads() -> None:
    cfg = load_config(_RUNTIME_YAML)
    assert isinstance(cfg, AppConfig)
    assert cfg.runtime.version == "0.1.0"
    assert cfg.http.port == 8000
    assert cfg.approvals.default_ttl_seconds == 900
    assert cfg.evidence.hash_algorithm == "sha256"


def test_config_defaults() -> None:
    # Omitted sub-fields fall back to model defaults.
    cfg = AppConfig.model_validate(
        {
            "runtime": {},
            "http": {},
            "approvals": {},
            "evidence": {},
        }
    )
    assert cfg.runtime.default_disposition == "allow_with_flag"
    assert cfg.http.host == "0.0.0.0"
    assert cfg.approvals.max_pending_per_role == 500


def test_config_extra_field_forbidden() -> None:
    with pytest.raises(Exception):
        AppConfig.model_validate(
            {
                "runtime": {"surprise": 1},
                "http": {},
                "approvals": {},
                "evidence": {},
            }
        )


def test_malformed_config_raises_config_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("runtime: [not, a, mapping]\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(str(bad))


def test_missing_config_file_raises_config_error(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.yaml"
    with pytest.raises(ConfigError):
        load_config(str(missing))
