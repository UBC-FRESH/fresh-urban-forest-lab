"""Tests for robust vertical-control estimates."""

from __future__ import annotations

import numpy as np
import pytest

from fresh_urban_forest.vertical_control import estimate_control_offset


def test_estimate_control_offset_recovers_synthetic_offset() -> None:
    """A robust median recovers the offset despite outliers."""
    values = np.concatenate(
        [
            np.random.default_rng(7).normal(0.4, 0.08, 5_000),
            np.array([-8.0, 7.0, 12.0, -5.0]),
        ]
    )
    estimate = estimate_control_offset(values, surface="ground", bootstrap_samples=300, seed=3)
    assert estimate.surface == "ground"
    assert estimate.count == 5_000
    assert estimate.offset_m == pytest.approx(0.4, abs=0.02)
    assert estimate.bootstrap_low_m <= estimate.offset_m <= estimate.bootstrap_high_m
    assert estimate.median_abs_deviation_m < 0.1
    payload = estimate.to_dict()
    assert payload["method"] == "paired-stable-surface-median"
    assert payload["count"] == 5_000


def test_estimate_control_offset_rejects_empty_and_bad_limits() -> None:
    """Empty observations and invalid limits are explicit errors."""
    with pytest.raises(ValueError, match="no finite"):
        estimate_control_offset([], surface="ground")
    with pytest.raises(ValueError, match="max_abs_m"):
        estimate_control_offset([0.1], surface="ground", max_abs_m=0.0)
    with pytest.raises(ValueError, match="bootstrap_samples"):
        estimate_control_offset([0.1], surface="ground", bootstrap_samples=0)
