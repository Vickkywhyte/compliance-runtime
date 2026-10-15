"""Tests for Ed25519 signing + verification (ADR-004, C-13)."""

from __future__ import annotations

import base64
from collections.abc import Iterator
from pathlib import Path

import pytest

from compliance_runtime.config.keys import get_or_create_signing_key, set_keys_dir
from compliance_runtime.evidence.signing import (
    export_public_key_pem,
    get_key_id,
    sign_hash,
    verify_signature,
)

_HASH = "a" * 64


@pytest.fixture(autouse=True)
def _temp_keys(tmp_path: Path) -> Iterator[None]:
    set_keys_dir(tmp_path)
    get_or_create_signing_key()  # generate the pair into tmp_path
    try:
        yield
    finally:
        set_keys_dir(None)


def test_sign_hash_returns_base64_string() -> None:
    sig = sign_hash(_HASH)
    assert isinstance(sig, str)
    # Round-trips through base64 without error.
    assert base64.b64decode(sig)


def test_verify_signature_returns_true_for_valid() -> None:
    assert verify_signature(_HASH, sign_hash(_HASH)) is True


def test_verify_signature_returns_false_for_invalid() -> None:
    assert verify_signature(_HASH, base64.b64encode(b"bogus").decode()) is False


def test_verify_signature_returns_false_for_wrong_hash() -> None:
    sig = sign_hash(_HASH)
    assert verify_signature("b" * 64, sig) is False


def test_get_key_id_is_deterministic() -> None:
    assert len(get_key_id()) == 16
    assert all(c in "0123456789abcdef" for c in get_key_id())


def test_get_key_id_stable_across_calls() -> None:
    assert get_key_id() == get_key_id()


def test_signature_is_deterministic() -> None:
    # Ed25519: same message + same key → same signature.
    assert sign_hash(_HASH) == sign_hash(_HASH)


def test_export_public_key_pem_format() -> None:
    pem = export_public_key_pem()
    assert pem.startswith("-----BEGIN PUBLIC KEY-----")
    assert "-----END PUBLIC KEY-----" in pem
