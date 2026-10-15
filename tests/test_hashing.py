"""Tests for evidence canonicalization + SHA-256 hashing (05_DATA_SPEC §8)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from compliance_runtime.evidence.hashing import (
    GENESIS_HASH,
    canonicalize,
    compute_current_hash,
    verify_hash,
)

_VECTORS = json.loads(
    Path("tests/fixtures/known_hash_vectors.json").read_text(encoding="utf-8")
)["vectors"]


def test_canonicalize_sorts_keys() -> None:
    assert canonicalize({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_canonicalize_no_whitespace() -> None:
    out = canonicalize({"a": 1, "b": [1, 2]})
    assert " " not in out


def test_canonicalize_handles_datetime() -> None:
    dt = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    assert canonicalize({"t": dt}) == '{"t":"2026-01-02T03:04:05+00:00"}'


def test_canonicalize_handles_nested_structures() -> None:
    assert canonicalize({"x": {"y": [1, 2, 3]}}) == '{"x":{"y":[1,2,3]}}'


def test_canonicalize_deterministic() -> None:
    obj = {"b": 1, "a": {"y": 2, "x": 3}, "c": [3, 2, 1]}
    outputs = {canonicalize(dict(obj)) for _ in range(100)}
    assert len(outputs) == 1


def test_canonicalize_handles_unicode() -> None:
    assert canonicalize({"n": "café"}) == '{"n":"café"}'
    assert canonicalize({"n": "naïve"}) == '{"n":"naïve"}'
    assert canonicalize({"n": "日本語"}) == '{"n":"日本語"}'


def test_compute_current_hash_known_vector() -> None:
    for vector in _VECTORS:
        assert canonicalize(vector["fields"]) == vector["expected_canonical"]
        assert (
            compute_current_hash(vector["fields"], vector["previous_hash"])
            == vector["expected_hash"]
        )


def test_compute_current_hash_includes_previous_hash() -> None:
    a = compute_current_hash({"a": 1}, "PREV_A")
    b = compute_current_hash({"a": 1}, "PREV_B")
    assert a != b


def test_compute_current_hash_different_for_different_records() -> None:
    a = compute_current_hash({"a": 1}, GENESIS_HASH)
    b = compute_current_hash({"a": 2}, GENESIS_HASH)
    assert a != b


def test_compute_current_hash_stable_across_calls() -> None:
    hashes = {compute_current_hash({"a": 1, "b": "x"}, GENESIS_HASH) for _ in range(10)}
    assert len(hashes) == 1


def test_verify_hash_returns_true_for_correct() -> None:
    h = compute_current_hash({"a": 1}, GENESIS_HASH)
    assert verify_hash({"a": 1}, GENESIS_HASH, h) is True


def test_verify_hash_returns_false_for_tampered() -> None:
    h = compute_current_hash({"a": 1}, GENESIS_HASH)
    assert verify_hash({"a": 2}, GENESIS_HASH, h) is False


def test_genesis_hash_is_string_constant() -> None:
    assert GENESIS_HASH == "GENESIS"
    assert isinstance(GENESIS_HASH, str)
