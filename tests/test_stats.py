"""Tests for statistical helpers (06_EVAL_SPEC §7, §8)."""

from __future__ import annotations

import numpy as np
import pytest

from compliance_runtime.evaluation.stats import bootstrap_ci, percentile


def test_bootstrap_ci_accepts_list() -> None:
    lo, hi = bootstrap_ci([0.0, 1.0, 0.0, 1.0], seed=0)
    assert lo <= hi


def test_bootstrap_ci_accepts_numpy_array() -> None:
    lo, hi = bootstrap_ci(np.array([0.0, 1.0, 0.0, 1.0]), seed=0)
    assert lo <= hi


def test_bootstrap_ci_empty_raises() -> None:
    with pytest.raises(ValueError):
        bootstrap_ci([])


def test_bootstrap_ci_deterministic_with_seed() -> None:
    values = [0.1, 0.9, 0.5, 0.3, 0.7]
    assert bootstrap_ci(values, seed=42) == bootstrap_ci(values, seed=42)


def test_bootstrap_ci_constant_distribution_tight() -> None:
    lo, hi = bootstrap_ci([0.75] * 50, seed=0)
    assert lo == hi == 0.75


def test_bootstrap_ci_contains_mean() -> None:
    values = [0.2, 0.4, 0.6, 0.8, 1.0]
    lo, hi = bootstrap_ci(values, seed=0)
    assert lo <= float(np.mean(values)) <= hi


def test_percentile_p50_median() -> None:
    assert percentile([10, 20, 30], 50) == 20.0


def test_percentile_p95() -> None:
    assert percentile([10000, 20000, 30000, 40000, 50000], 95) == pytest.approx(48000.0)
