"""Typed configuration models (Pydantic v2, ``extra="forbid"``).

Mirrors ``configs/runtime.yaml`` (05_DATA_SPEC §4.1) and
``configs/eval.yaml`` (05_DATA_SPEC §4.3). ``extra="forbid"`` means an
unknown key anywhere in a config file is a hard error (ADR-008) — config
mistakes fail loud at startup rather than being silently ignored.

``AppConfig`` is the root model for ``runtime.yaml``; it composes the four
section models named in the Phase 1 spec (RuntimeConfig, HTTPConfig,
ApprovalsConfig, EvidenceConfig).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Disposition = Literal["allow", "deny", "require_approval", "allow_with_flag"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class RuntimeConfig(BaseModel):
    """The ``runtime:`` section of ``runtime.yaml``."""

    model_config = ConfigDict(extra="forbid")

    version: str = "0.1.0"
    default_disposition: Disposition = "allow_with_flag"
    evidence_store_path: str = "data/runtime.db"
    keys_dir: str = "~/.compliance-runtime/keys"
    log_level: LogLevel = "INFO"


class HTTPConfig(BaseModel):
    """The ``http:`` section of ``runtime.yaml``."""

    model_config = ConfigDict(extra="forbid")

    host: str = "0.0.0.0"
    port: int = 8000
    request_timeout_seconds: int = 30


class ApprovalsConfig(BaseModel):
    """The ``approvals:`` section of ``runtime.yaml``."""

    model_config = ConfigDict(extra="forbid")

    default_ttl_seconds: int = 900
    max_pending_per_role: int = 500


class EvidenceConfig(BaseModel):
    """The ``evidence:`` section of ``runtime.yaml``."""

    model_config = ConfigDict(extra="forbid")

    hash_algorithm: Literal["sha256"] = "sha256"
    signature_algorithm: Literal["ed25519"] = "ed25519"


class AppConfig(BaseModel):
    """Root model for ``configs/runtime.yaml``."""

    model_config = ConfigDict(extra="forbid")

    runtime: RuntimeConfig
    http: HTTPConfig
    approvals: ApprovalsConfig
    evidence: EvidenceConfig


class EvalMetricsConfig(BaseModel):
    """The ``metrics:`` section of ``eval.yaml``."""

    model_config = ConfigDict(extra="forbid")

    enforcement: list[str]
    evidence: list[str]
    oversight: list[str]


class EvalConfig(BaseModel):
    """Root model for ``configs/eval.yaml`` (05_DATA_SPEC §4.3)."""

    model_config = ConfigDict(extra="forbid")

    benchmark_path: str
    metrics: EvalMetricsConfig
    bootstrap_samples: int = Field(default=1000, ge=1)
    seed: int = 0


def _self_test() -> None:
    """Build each model from spec defaults and verify extra-key rejection."""
    from pydantic import ValidationError

    app = AppConfig(
        runtime=RuntimeConfig(),
        http=HTTPConfig(),
        approvals=ApprovalsConfig(),
        evidence=EvidenceConfig(),
    )
    assert app.runtime.default_disposition == "allow_with_flag"
    assert app.http.port == 8000

    try:
        RuntimeConfig.model_validate({"unexpected": 1})
    except ValidationError:
        pass
    else:  # pragma: no cover
        raise AssertionError("extra='forbid' did not reject unknown key")

    EvalConfig.model_validate(
        {
            "benchmark_path": "data/eval/benchmark.jsonl",
            "metrics": {"enforcement": [], "evidence": [], "oversight": []},
            "bootstrap_samples": 1000,
            "seed": 0,
        }
    )
    print("config.models self-test: PASS")


if __name__ == "__main__":
    _self_test()
