"""Ed25519 signing and verification (ADR-004, ADR-017, C-13, C-18, C-20).

This is the ONLY module (besides ``config/keys.py``, which handles the key
lifecycle) that touches private key material. All other modules sign and
verify through the ``sign_hash`` / ``verify_signature`` API and never load the
private key themselves (C-18). Ed25519 is deterministic: the same hash and key
always yield the same signature.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization

from compliance_runtime.config.keys import (
    get_or_create_signing_key,
    load_public_key,
)


def sign_hash(current_hash: str) -> str:
    """Sign ``current_hash`` with the private key; return base64 signature."""
    private_key = get_or_create_signing_key()
    signature = private_key.sign(current_hash.encode("utf-8"))
    return base64.b64encode(signature).decode("ascii")


def verify_signature(current_hash: str, signature: str) -> bool:
    """Return True if ``signature`` is valid for ``current_hash``.

    Returns False on an invalid or malformed signature; never raises.
    """
    public_key = load_public_key()
    try:
        raw = base64.b64decode(signature)
    except (ValueError, TypeError):
        return False
    try:
        public_key.verify(raw, current_hash.encode("utf-8"))
        return True
    except InvalidSignature:
        return False


def get_key_id() -> str:
    """Return a stable id for the current key: sha256(DER pubkey)[:16].

    Derives the public key from the signing key pair (generating it on first
    run if absent), so this works even before the first signature is made.
    """
    public_key = get_or_create_signing_key().public_key()
    der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(der).hexdigest()[:16]


def export_public_key_pem() -> str:
    """Return the PEM-encoded public key (safe to export; never private)."""
    public_key = load_public_key()
    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return pem.decode("ascii")


def _self_test() -> None:
    """Sign a hash in a temp key dir and verify round-trip behavior."""
    import tempfile

    from compliance_runtime.config.keys import set_keys_dir

    try:
        with tempfile.TemporaryDirectory() as tmp:
            set_keys_dir(tmp)
            get_or_create_signing_key()  # generate into tmp
            digest = "a" * 64
            sig = sign_hash(digest)
            assert verify_signature(digest, sig) is True
            assert verify_signature("b" * 64, sig) is False
            assert sign_hash(digest) == sig  # Ed25519 is deterministic
            assert len(get_key_id()) == 16
            assert export_public_key_pem().startswith("-----BEGIN PUBLIC KEY-----")
    finally:
        set_keys_dir(None)  # restore default keys dir
    print("evidence.signing self-test: PASS")


if __name__ == "__main__":
    _self_test()
