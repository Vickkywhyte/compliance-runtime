"""The single configuration entry point (Lesson 8).

This is the ONLY module permitted to read ``os.getenv`` / ``os.environ``.
Every other module imports typed config from here. It loads ``.env`` via
``python-dotenv`` and parses the YAML config files into the Pydantic models
in :mod:`compliance_runtime.config.models`.

A lint rule (``grep -r "os.getenv" src/``) must return hits only in this
file.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import ValidationError

from compliance_runtime.config.models import AppConfig, EvalConfig
from compliance_runtime.exceptions import ConfigError

# Environment variable names (all reads of the environment live here).
_ENV_RUNTIME_CONFIG = "CR_RUNTIME_CONFIG"
_ENV_EVAL_CONFIG = "CR_EVAL_CONFIG"
_ENV_KEYS_DIR = "CR_KEYS_DIR"
_ENV_LOG_LEVEL = "CR_LOG_LEVEL"

_DEFAULT_RUNTIME_CONFIG = "configs/runtime.yaml"
_DEFAULT_EVAL_CONFIG = "configs/eval.yaml"

# Substrings that mark an env var name as holding a secret (C-15 scrubber).
_SECRET_NAME_MARKERS = ("KEY", "TOKEN", "SECRET", "PEM")

_dotenv_loaded = False


def _ensure_dotenv() -> None:
    """Load ``.env`` once per process (idempotent)."""
    global _dotenv_loaded
    if not _dotenv_loaded:
        load_dotenv()
        _dotenv_loaded = True


def _read_yaml(path: Path) -> dict[str, Any]:
    """Read and parse a YAML file into a dict, raising ConfigError on failure."""
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Malformed YAML in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"Config root must be a mapping: {path}")
    return raw


def runtime_config_path(override: str | None = None) -> Path:
    """Resolve the runtime config path from arg, env, then default."""
    _ensure_dotenv()
    return Path(
        override or os.getenv(_ENV_RUNTIME_CONFIG, _DEFAULT_RUNTIME_CONFIG)
    )


def eval_config_path(override: str | None = None) -> Path:
    """Resolve the eval config path from arg, env, then default."""
    _ensure_dotenv()
    return Path(override or os.getenv(_ENV_EVAL_CONFIG, _DEFAULT_EVAL_CONFIG))


def load_config(path: str | None = None) -> AppConfig:
    """Load and validate ``runtime.yaml`` into an :class:`AppConfig`.

    A log-level override from ``CR_LOG_LEVEL`` is applied if present.
    Raises :class:`ConfigError` on a missing file, malformed YAML, or a
    schema violation.
    """
    _ensure_dotenv()
    cfg_path = runtime_config_path(path)
    raw = _read_yaml(cfg_path)

    log_override = os.getenv(_ENV_LOG_LEVEL)
    if log_override and isinstance(raw.get("runtime"), dict):
        raw["runtime"]["log_level"] = log_override

    try:
        return AppConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"Invalid runtime config {cfg_path}: {exc}") from exc


def load_eval_config(path: str | None = None) -> EvalConfig:
    """Load and validate ``eval.yaml`` into an :class:`EvalConfig`."""
    _ensure_dotenv()
    cfg_path = eval_config_path(path)
    raw = _read_yaml(cfg_path)
    try:
        return EvalConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"Invalid eval config {cfg_path}: {exc}") from exc


def keys_dir(config: AppConfig | None = None) -> Path:
    """Resolve the signing-key directory (env override wins, then config)."""
    _ensure_dotenv()
    raw = os.getenv(_ENV_KEYS_DIR)
    if not raw:
        raw = config.runtime.keys_dir if config else "~/.compliance-runtime/keys"
    return Path(raw).expanduser()


def sensitive_env_values() -> frozenset[str]:
    """Return the set of env-var values whose names look secret.

    Used by the logging scrubber (C-15). Keeping this here means the
    logging module never reads the environment directly (Lesson 8).
    """
    _ensure_dotenv()
    values: set[str] = set()
    for name, value in os.environ.items():
        upper = name.upper()
        if value and any(marker in upper for marker in _SECRET_NAME_MARKERS):
            values.add(value)
    return frozenset(values)


def _self_test() -> None:
    """Load the shipped configs and confirm malformed config raises."""
    import tempfile

    cfg = load_config()
    assert cfg.runtime.version, cfg
    assert cfg.http.port == 8000, cfg

    eval_cfg = load_eval_config()
    assert eval_cfg.bootstrap_samples >= 1, eval_cfg

    with tempfile.NamedTemporaryFile(
        "w", suffix=".yaml", delete=False
    ) as handle:
        handle.write("runtime: [this, is, not, a, mapping]\n")
        bad_path = handle.name
    try:
        load_config(bad_path)
    except ConfigError:
        pass
    else:  # pragma: no cover
        raise AssertionError("malformed config did not raise ConfigError")
    finally:
        os.unlink(bad_path)

    print("config.loader self-test: PASS")


if __name__ == "__main__":
    _self_test()
