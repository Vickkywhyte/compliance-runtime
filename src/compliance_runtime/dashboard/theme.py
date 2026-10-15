"""Color palettes for the dashboard (no external CSS; inline styles only)."""

from __future__ import annotations

_SEVERITY_COLORS: dict[str, str] = {
    "low": "#2e7d32",       # green
    "medium": "#f9a825",    # amber
    "high": "#ef6c00",      # orange
    "critical": "#c62828",  # red
}

_DISPOSITION_COLORS: dict[str, str] = {
    "allow": "#2e7d32",            # green
    "deny": "#c62828",            # red
    "require_approval": "#f9a825",  # amber
    "allow_with_flag": "#1565c0",   # blue
}

_NEUTRAL = "#616161"


def severity_color(severity: str) -> str:
    """Return the hex color for a severity level (neutral if unknown)."""
    return _SEVERITY_COLORS.get(severity, _NEUTRAL)


def disposition_color(disposition: str) -> str:
    """Return the hex color for a disposition (neutral if unknown)."""
    return _DISPOSITION_COLORS.get(disposition, _NEUTRAL)


def _self_test() -> None:
    assert severity_color("critical") == "#c62828"
    assert disposition_color("allow") == "#2e7d32"
    assert severity_color("unknown") == _NEUTRAL
    print("dashboard.theme self-test: PASS")


if __name__ == "__main__":
    _self_test()
