"""Per-agent, per-action in-memory rate limiter (C-32, 09_RUNTIME_DESIGN §5).

Sliding 60-second window per ``(agent_id, action)``. Thread-safe. In-process
counters are sufficient for the single-process v1 deployment; a shared
counter (Redis/SQLite) is a v2 concern.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

_WINDOW_SECONDS = 60.0


class RateLimiter:
    """Thread-safe sliding-window rate limiter."""

    def __init__(self, default_limit_per_minute: int = 100) -> None:
        self._limit = default_limit_per_minute
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._rejections: dict[tuple[str, str], int] = defaultdict(int)
        self._lock = threading.Lock()

    @staticmethod
    def _key(agent_id: str, action: str) -> tuple[str, str]:
        return (agent_id, action)

    def _prune(self, events: deque[float], now: float) -> None:
        cutoff = now - _WINDOW_SECONDS
        while events and events[0] <= cutoff:
            events.popleft()

    def check(self, agent_id: str, action: str) -> tuple[bool, int]:
        """Return ``(allowed, current_count)`` without recording the call.

        ``allowed`` is False when recording another call would exceed the
        limit. A rejection increments the per-key drop metric.
        """
        key = self._key(agent_id, action)
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            self._prune(events, now)
            count = len(events)
            allowed = count < self._limit
            if not allowed:
                self._rejections[key] += 1
            return allowed, count

    def record(self, agent_id: str, action: str) -> None:
        """Record a call that passed the rate gate."""
        key = self._key(agent_id, action)
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            self._prune(events, now)
            events.append(now)

    def snapshot(self) -> dict[str, int]:
        """Return current in-window counts per ``"agent_id:action"`` key."""
        now = time.monotonic()
        with self._lock:
            result: dict[str, int] = {}
            for (agent_id, action), events in self._events.items():
                self._prune(events, now)
                if events:
                    result[f"{agent_id}:{action}"] = len(events)
            return result

    def drops(self) -> dict[str, int]:
        """Return cumulative rejection counts per ``"agent_id:action"`` key."""
        with self._lock:
            return {
                f"{agent_id}:{action}": n
                for (agent_id, action), n in self._rejections.items()
            }


def _self_test() -> None:
    """Exercise the gate: allow up to the limit, then reject."""
    limiter = RateLimiter(default_limit_per_minute=3)
    for _ in range(3):
        allowed, _ = limiter.check("a", "x")
        assert allowed
        limiter.record("a", "x")
    allowed, count = limiter.check("a", "x")
    assert not allowed and count == 3, (allowed, count)
    assert limiter.snapshot()["a:x"] == 3
    assert limiter.drops()["a:x"] == 1
    print("policy.rate_limit self-test: PASS")


if __name__ == "__main__":
    _self_test()
