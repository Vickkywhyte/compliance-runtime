"""Statistical helpers: percentiles + bootstrap CI (06_EVAL_SPEC §7, §8).

Deterministic given a fixed seed: the bootstrap uses a seeded numpy generator,
so the same values + seed always yield the same interval.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def percentile(values: Sequence[float] | np.ndarray, p: float) -> float:
    """Return the ``p``-th percentile (0–100) of ``values`` (linear interp)."""
    array = np.asarray(list(values), dtype=float)
    if array.size == 0:
        raise ValueError("percentile() requires a non-empty sequence")
    return float(np.percentile(array, p))


def bootstrap_ci(
    values: Sequence[float] | np.ndarray,
    n_samples: int = 1000,
    confidence: float = 0.95,
    seed: int = 0,
) -> tuple[float, float]:
    """Return the ``confidence`` bootstrap CI of the mean of ``values``.

    Deterministic for a given ``seed``. Raises :class:`ValueError` on empty
    input. With a constant distribution the interval collapses to that value.
    """
    array = np.asarray(list(values), dtype=float)
    if array.size == 0:
        raise ValueError("bootstrap_ci() requires a non-empty sequence")

    rng = np.random.default_rng(seed)
    n = array.size
    means = np.empty(n_samples, dtype=float)
    for i in range(n_samples):
        sample = array[rng.integers(0, n, size=n)]
        means[i] = sample.mean()

    alpha = (1.0 - confidence) / 2.0
    lower = float(np.percentile(means, alpha * 100.0))
    upper = float(np.percentile(means, (1.0 - alpha) * 100.0))
    return lower, upper


def mean_ci_half_width(lo: float, hi: float) -> float:
    """Return half the width of a CI (used by the regression policy)."""
    return (hi - lo) / 2.0


def _self_test() -> None:
    """Verify determinism, empty-input error, and constant-distribution CI."""
    assert percentile([10, 20, 30], 50) == 20.0
    a = bootstrap_ci([1.0, 2.0, 3.0, 4.0], seed=0)
    b = bootstrap_ci([1.0, 2.0, 3.0, 4.0], seed=0)
    assert a == b, (a, b)
    lo, hi = bootstrap_ci([0.5] * 10, seed=0)
    assert lo == hi == 0.5
    try:
        bootstrap_ci([])
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("empty input did not raise")
    print("evaluation.stats self-test: PASS")


if __name__ == "__main__":
    _self_test()
