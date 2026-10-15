"""ID generation, UTC time, and canonical JSON serialization.

- :func:`new_ulid` — lexicographically sortable 26-char ULID.
- :func:`now_utc` — timezone-aware UTC ``datetime``.
- :func:`canonical_json` — deterministic serialization for hashing
  (sorted keys, no whitespace, ISO-8601 UTC datetimes). See
  ``claude_chat/05_DATA_SPEC.md`` §8.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import ulid


def new_ulid() -> str:
    """Return a new ULID as a 26-character Crockford base32 string."""
    return str(ulid.new())


def now_utc() -> datetime:
    """Return the current time as a timezone-aware UTC ``datetime``."""
    return datetime.now(timezone.utc)


def _json_default(value: Any) -> str:
    """Serialize values that ``json`` cannot handle natively.

    ``datetime`` is rendered as ISO-8601. Naive datetimes are treated as
    UTC so serialization stays deterministic (05_DATA_SPEC §8).
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    raise TypeError(f"Type {type(value).__name__} is not JSON serializable")


def canonical_json(obj: dict[str, Any]) -> str:
    """Return a canonical JSON string for ``obj``.

    Keys are sorted alphabetically, there is no whitespace, and datetimes
    are rendered as ISO-8601 UTC. The output is deterministic: the same
    logical input always produces the same string, which is a precondition
    for the evidence hash chain.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    )


def _self_test() -> None:
    """Verify observable behavior of the ID/serialization helpers."""
    u = new_ulid()
    assert len(u) == 26, f"ULID length {len(u)} != 26"
    assert len({new_ulid() for _ in range(100)}) == 100, "ULIDs not unique"

    t = now_utc()
    assert t.tzinfo is not None, "now_utc() must be timezone-aware"

    a = canonical_json({"b": 1, "a": 2})
    b = canonical_json({"a": 2, "b": 1})
    assert a == b == '{"a":2,"b":1}', a

    dt = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    assert canonical_json({"t": dt}) == '{"t":"2026-01-02T03:04:05+00:00"}'

    print("ids self-test: PASS")


if __name__ == "__main__":
    _self_test()
