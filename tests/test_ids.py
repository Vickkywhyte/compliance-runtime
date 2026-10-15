"""Tests for ID generation and canonical JSON (05_DATA_SPEC §6, §8)."""

from __future__ import annotations

from datetime import datetime, timezone

from compliance_runtime.utils.ids import canonical_json, new_ulid, now_utc


def test_new_ulid_length() -> None:
    assert len(new_ulid()) == 26


def test_new_ulid_uniqueness() -> None:
    ulids = {new_ulid() for _ in range(100)}
    assert len(ulids) == 100


def test_now_utc_is_timezone_aware() -> None:
    t = now_utc()
    assert t.tzinfo is not None
    assert t.utcoffset() == timezone.utc.utcoffset(None)


def test_canonical_json_is_deterministic() -> None:
    obj = {"b": 1, "a": {"y": 2, "x": 3}, "c": [1, 2, 3]}
    assert canonical_json(obj) == canonical_json(dict(obj))


def test_canonical_json_sorts_keys() -> None:
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_canonical_json_handles_datetime() -> None:
    dt = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    assert canonical_json({"t": dt}) == '{"t":"2026-01-02T03:04:05+00:00"}'
