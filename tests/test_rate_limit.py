"""Tests for the per-agent rate limiter (C-32, Lesson 6 concurrency)."""

from __future__ import annotations

import threading

from compliance_runtime.policy.rate_limit import RateLimiter


def test_allows_up_to_limit() -> None:
    limiter = RateLimiter(default_limit_per_minute=3)
    for _ in range(3):
        allowed, _ = limiter.check("a", "x")
        assert allowed
        limiter.record("a", "x")
    allowed, count = limiter.check("a", "x")
    assert not allowed
    assert count == 3


def test_record_increments_count() -> None:
    limiter = RateLimiter(default_limit_per_minute=10)
    _, before = limiter.check("a", "x")
    limiter.record("a", "x")
    _, after = limiter.check("a", "x")
    assert after == before + 1


def test_keys_are_independent() -> None:
    limiter = RateLimiter(default_limit_per_minute=1)
    limiter.record("a", "x")
    # Different agent and different action are unaffected.
    assert limiter.check("b", "x")[0] is True
    assert limiter.check("a", "y")[0] is True
    assert limiter.check("a", "x")[0] is False


def test_snapshot_reports_counts() -> None:
    limiter = RateLimiter(default_limit_per_minute=10)
    limiter.record("a", "x")
    limiter.record("a", "x")
    assert limiter.snapshot()["a:x"] == 2


def test_drops_metric_counts_rejections() -> None:
    limiter = RateLimiter(default_limit_per_minute=1)
    limiter.record("a", "x")
    limiter.check("a", "x")  # rejected
    limiter.check("a", "x")  # rejected
    assert limiter.drops()["a:x"] == 2


def test_thread_safe_under_concurrency() -> None:
    limiter = RateLimiter(default_limit_per_minute=1000)

    def worker() -> None:
        for _ in range(100):
            allowed, _ = limiter.check("a", "x")
            if allowed:
                limiter.record("a", "x")

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # 10 threads * 100 calls = 1000 records, exactly at the limit.
    assert limiter.snapshot()["a:x"] == 1000
