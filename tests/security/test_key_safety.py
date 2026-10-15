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


# --- Phase 4: Ed25519 signing safety (C-13, C-18, C-20) ------------------


def test_signature_verifies_after_key_reload(tmp_path: Path) -> None:
    # Sign, drop the in-memory key, reload from disk, and verify.
    import importlib

    from compliance_runtime.config.keys import set_keys_dir
    from compliance_runtime.evidence import signing

    set_keys_dir(tmp_path)
    try:
        get_or_create_signing_key()
        sig = signing.sign_hash("c" * 64)
        importlib.reload(signing)  # no cached key state survives
        set_keys_dir(tmp_path)  # reload() reset module globals
        assert signing.verify_signature("c" * 64, sig) is True
    finally:
        set_keys_dir(None)


def test_private_key_not_in_any_test_fixture() -> None:
    marker = "-----BEGIN PRIVATE KEY-----"
    for path in Path("tests/fixtures").glob("*.json"):
        assert marker not in path.read_text(encoding="utf-8"), path


def test_signing_module_is_only_importer_of_crypto_private_key() -> None:
    # Only config/keys.py and evidence/signing.py may import the Ed25519
    # private-key primitive; everyone else uses sign_hash/verify_signature.
    src = Path("src/compliance_runtime")
    needle = "from cryptography.hazmat.primitives.asymmetric.ed25519 import"
    importers = {
        str(p.relative_to(src))
        for p in src.rglob("*.py")
        if needle in p.read_text(encoding="utf-8")
    }
    assert importers == {"config/keys.py"}, importers
