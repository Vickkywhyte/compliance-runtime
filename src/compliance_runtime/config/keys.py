"""Signing-key lifecycle (ADR-017, C-15 to C-20).

One Ed25519 key pair per runtime instance, generated on first run:

- private key -> ``<keys_dir>/signing_key.pem`` (PKCS8 PEM, mode 0600)
- public key  -> ``<keys_dir>/verification_key.pem`` (mode 0644)

Key material is NEVER logged. This module only creates/loads keys; signing
itself is confined to ``evidence/signing.py`` in a later phase (C-18).
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from compliance_runtime.exceptions import SigningKeyError

_PRIVATE_KEY_NAME = "signing_key.pem"
_PUBLIC_KEY_NAME = "verification_key.pem"
_DEFAULT_KEYS_DIR = "~/.compliance-runtime/keys"

_PRIVATE_MODE = 0o600
_PUBLIC_MODE = 0o644
_DIR_MODE = 0o700


def _resolve_dir(keys_dir: str | os.PathLike[str] | None) -> Path:
    raw = str(keys_dir) if keys_dir is not None else _DEFAULT_KEYS_DIR
    return Path(raw).expanduser()


def private_key_path(keys_dir: str | os.PathLike[str] | None = None) -> Path:
    """Return the resolved path to the private signing key."""
    return _resolve_dir(keys_dir) / _PRIVATE_KEY_NAME


def public_key_path(keys_dir: str | os.PathLike[str] | None = None) -> Path:
    """Return the resolved path to the public verification key."""
    return _resolve_dir(keys_dir) / _PUBLIC_KEY_NAME


def _write_private_key(path: Path, key: Ed25519PrivateKey) -> None:
    """Write the private key as PKCS8 PEM with mode 0600."""
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    # Create with restrictive permissions from the start, then enforce.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, _PRIVATE_MODE)
    try:
        os.write(fd, pem)
    finally:
        os.close(fd)
    os.chmod(path, _PRIVATE_MODE)


def _write_public_key(path: Path, key: Ed25519PublicKey) -> None:
    """Write the public key as SubjectPublicKeyInfo PEM with mode 0644."""
    pem = key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    path.write_bytes(pem)
    os.chmod(path, _PUBLIC_MODE)


def get_or_create_signing_key(
    keys_dir: str | os.PathLike[str] | None = None,
) -> Ed25519PrivateKey:
    """Load the Ed25519 signing key, generating it on first run.

    On first run, generates a key pair, writes the private key with mode
    0600 and exports the public key with mode 0644. Never logs key
    material. Raises :class:`SigningKeyError` on an unreadable key file.
    """
    directory = _resolve_dir(keys_dir)
    priv_path = directory / _PRIVATE_KEY_NAME
    pub_path = directory / _PUBLIC_KEY_NAME

    if priv_path.exists():
        try:
            data = priv_path.read_bytes()
            loaded = serialization.load_pem_private_key(data, password=None)
        except (ValueError, TypeError) as exc:
            raise SigningKeyError(
                f"Could not load signing key at {priv_path}"
            ) from exc
        if not isinstance(loaded, Ed25519PrivateKey):
            raise SigningKeyError(
                f"Key at {priv_path} is not an Ed25519 private key"
            )
        # Ensure the public key is present for verification (C-19).
        if not pub_path.exists():
            _write_public_key(pub_path, loaded.public_key())
        return loaded

    directory.mkdir(parents=True, exist_ok=True)
    os.chmod(directory, _DIR_MODE)
    key = Ed25519PrivateKey.generate()
    _write_private_key(priv_path, key)
    _write_public_key(pub_path, key.public_key())
    return key


def load_public_key(
    keys_dir: str | os.PathLike[str] | None = None,
) -> Ed25519PublicKey:
    """Load the public verification key."""
    path = public_key_path(keys_dir)
    if not path.exists():
        raise SigningKeyError(f"Public key not found: {path}")
    try:
        loaded = serialization.load_pem_public_key(path.read_bytes())
    except ValueError as exc:
        raise SigningKeyError(f"Could not load public key at {path}") from exc
    if not isinstance(loaded, Ed25519PublicKey):
        raise SigningKeyError(f"Key at {path} is not an Ed25519 public key")
    return loaded


def _file_mode(path: Path) -> int:
    """Return the permission bits of ``path`` (e.g. 0o600)."""
    return stat.S_IMODE(path.stat().st_mode)


def _self_test() -> None:
    """Generate a key in a temp dir and verify files, modes, and reload."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        key = get_or_create_signing_key(tmp)
        assert isinstance(key, Ed25519PrivateKey)

        priv = private_key_path(tmp)
        pub = public_key_path(tmp)
        assert priv.exists() and pub.exists()
        assert _file_mode(priv) == _PRIVATE_MODE, oct(_file_mode(priv))

        # Second call must load the same key, not regenerate it.
        again = get_or_create_signing_key(tmp)
        assert again.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        ) == key.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        )

        pubkey = load_public_key(tmp)
        assert isinstance(pubkey, Ed25519PublicKey)

    print("config.keys self-test: PASS")


if __name__ == "__main__":
    _self_test()
