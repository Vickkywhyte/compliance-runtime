"""Signing-key safety tests (C-15 to C-20)."""

from __future__ import annotations

import json
import logging
import stat
from pathlib import Path

from cryptography.hazmat.primitives import serialization

from compliance_runtime.config.keys import (
    get_or_create_signing_key,
    private_key_path,
    public_key_path,
)
from compliance_runtime.utils.logging import configure_logging, get_logger

_GITIGNORE = Path(".gitignore")
_LOG_FILE = Path("logs/app.jsonl")


def test_signing_key_generation_creates_file(tmp_path: Path) -> None:
    get_or_create_signing_key(tmp_path)
    assert private_key_path(tmp_path).exists()


def test_signing_key_file_mode_is_0600(tmp_path: Path) -> None:
    get_or_create_signing_key(tmp_path)
    mode = stat.S_IMODE(private_key_path(tmp_path).stat().st_mode)
    assert mode == 0o600, oct(mode)


def test_public_key_exported(tmp_path: Path) -> None:
    get_or_create_signing_key(tmp_path)
    pub = public_key_path(tmp_path)
    assert pub.exists()
    mode = stat.S_IMODE(pub.stat().st_mode)
    assert mode == 0o644, oct(mode)


def test_private_key_not_in_log_output(tmp_path: Path) -> None:
    key = get_or_create_signing_key(tmp_path)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    configure_logging()
    # Attempt to log the private key material; the scrubber must redact it.
    get_logger("keytest").info("leak_attempt", key_material=pem)
    for handler in logging.getLogger().handlers:
        handler.flush()

    last = _LOG_FILE.read_text(encoding="utf-8").strip().splitlines()[-1]
    record = json.loads(last)
    assert "-----BEGIN PRIVATE KEY-----" not in last
    assert record["key_material"] == "[REDACTED_PEM]"


def test_signing_key_not_in_gitignore_negative() -> None:
    # Assert *.pem IS ignored (not the inverse).
    text = _GITIGNORE.read_text(encoding="utf-8")
    assert "*.pem" in text.splitlines()
