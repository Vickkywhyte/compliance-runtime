"""Prompt-injection marker filter for tool-call parameters (C-08, C-09).

Only string values are scanned. Numbers, booleans, and None are skipped.
The scan is case-insensitive and walks nested dicts and lists.
"""

from __future__ import annotations

from typing import Any

INJECTION_MARKERS: list[str] = [
    "<script",
    "</script",
    "ignore previous instructions",
    "ignore all previous",
    "system:",
    "assistant:",
    "user:",
    "developer:",
    "forget your instructions",
    "you are now",
    "new instructions:",
    "override:",
    "sudo:",
    "exec(",
    "eval(",
]


def contains_injection(value: str) -> str | None:
    """Return the first matched marker (lowercased), or None."""
    lowered = value.lower()
    for marker in INJECTION_MARKERS:
        if marker in lowered:
            return marker
    return None


def scan_parameters(parameters: Any) -> str | None:
    """Recursively scan all string values; return the first matched marker.

    Only strings are scanned (C-08). Non-string leaves are skipped.
    """
    if isinstance(parameters, str):
        return contains_injection(parameters)
    if isinstance(parameters, dict):
        for item in parameters.values():
            found = scan_parameters(item)
            if found is not None:
                return found
        return None
    if isinstance(parameters, (list, tuple)):
        for item in parameters:
            found = scan_parameters(item)
            if found is not None:
                return found
        return None
    return None


def _self_test() -> None:
    """Confirm markers are detected in nested structures and clean data passes."""
    assert contains_injection("Please IGNORE PREVIOUS INSTRUCTIONS now") == (
        "ignore previous instructions"
    )
    assert contains_injection("hello world") is None
    assert scan_parameters({"a": {"b": ["<script>x"]}}) == "<script"
    assert scan_parameters({"amount": 500, "ok": True, "n": None}) is None
    print("policy.injection self-test: PASS")


if __name__ == "__main__":
    _self_test()
