"""Canonical serialization + SHA-256 hash chain (05_DATA_SPEC §8, 09 §7.1–7.2).

``canonicalize`` is the single authoritative evidence serializer: deterministic
JSON with sorted keys, no whitespace, and typed defaults for ``datetime``,
``UUID``, ``Decimal``, and ``bytes``. The ``current_hash`` of a record binds
its canonical fields to the ``previous_hash`` of the chain.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

# The previous_hash of the first record in the chain (05_DATA_SPEC §6).
GENESIS_HASH = "GENESIS"

# Fields that are NOT part of the hashed payload (09_RUNTIME_DESIGN §7.2).
# Everything else on the record IS hashed — including signing_key_id.
_EXCLUDED_FIELDS = frozenset({"previous_hash", "current_hash", "signature"})


def _json_default(value: Any) -> str:
    """Serialize values json cannot handle natively, deterministically."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return base64.b64encode(bytes(value)).decode("ascii")
    raise TypeError(f"Type {type(value).__name__} is not JSON serializable")


def canonicalize(fields: dict[str, Any]) -> str:
    """Return the canonical JSON string for ``fields`` (deterministic)."""
    return json.dumps(
        fields,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    )


def record_hash_fields(record_fields: dict[str, Any]) -> dict[str, Any]:
    """Return the subset of fields that go into the hash (denylist)."""
    return {k: v for k, v in record_fields.items() if k not in _EXCLUDED_FIELDS}


def compute_current_hash(record_fields: dict[str, Any], previous_hash: str) -> str:
    """Compute a record's ``current_hash`` from its fields + ``previous_hash``."""
    canonical = canonicalize(record_hash_fields(record_fields))
    payload = canonical + "|" + previous_hash
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_hash(
    record_fields: dict[str, Any], previous_hash: str, expected_hash: str
) -> bool:
    """Return True if the recomputed hash matches ``expected_hash``."""
    return compute_current_hash(record_fields, previous_hash) == expected_hash


def sha256_hex(text: str) -> str:
    """Return the SHA-256 hex digest of a UTF-8 string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _self_test() -> None:
    """Verify determinism, key ordering, and field exclusion."""
    assert canonicalize({"b": 1, "a": 2}) == '{"a":2,"b":1}'
    assert canonicalize({"n": "café"}) == '{"n":"café"}'
    h1 = compute_current_hash({"a": 1}, GENESIS_HASH)
    h2 = compute_current_hash({"a": 1}, GENESIS_HASH)
    assert h1 == h2 and len(h1) == 64
    assert compute_current_hash({"a": 1}, "X") != compute_current_hash({"a": 1}, "Y")
    stripped = record_hash_fields(
        {"a": 1, "previous_hash": "p", "current_hash": "c", "signature": "s"}
    )
    assert stripped == {"a": 1}
    assert verify_hash({"a": 1}, GENESIS_HASH, h1)
    assert not verify_hash({"a": 2}, GENESIS_HASH, h1)
    print("evidence.hashing self-test: PASS")


if __name__ == "__main__":
    _self_test()
