"""Robust vertical control estimates for repeat LiDAR surfaces.

The module estimates a constant vertical offset from paired stable-surface observations.
It does not use canopy, tree, or model values as control and does not claim survey-grade
accuracy.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class ControlEstimate:
    """Robust offset estimate for one control surface.

    Attributes
    ----------
    surface : str
        Control-surface label.
    count : int
        Number of retained paired observations.
    offset_m : float
        Median 2018-minus-2022 difference in metres.
    median_abs_deviation_m : float
        Median absolute deviation of retained observations.
    percentile_25_m : float
        25th percentile.
    percentile_75_m : float
        75th percentile.
    bootstrap_low_m : float
        2.5th percentile of the bootstrap median.
    bootstrap_high_m : float
        97.5th percentile of the bootstrap median.
    max_abs_m : float
        Robust trimming threshold used.
    """

    surface: str
    count: int
    offset_m: float
    median_abs_deviation_m: float
    percentile_25_m: float
    percentile_75_m: float
    bootstrap_low_m: float
    bootstrap_high_m: float
    max_abs_m: float

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe estimate.

        Returns
        -------
        dict
            Estimate fields and method label.
        """
        return {
            "surface": self.surface,
            "count": self.count,
            "offset_m": round(self.offset_m, 4),
            "median_abs_deviation_m": round(self.median_abs_deviation_m, 4),
            "percentile_25_m": round(self.percentile_25_m, 4),
            "percentile_75_m": round(self.percentile_75_m, 4),
            "bootstrap_low_m": round(self.bootstrap_low_m, 4),
            "bootstrap_high_m": round(self.bootstrap_high_m, 4),
            "max_abs_m": self.max_abs_m,
            "method": "paired-stable-surface-median",
            "uncertainty": (
                "Robust median of paired 2018 minus 2022 stable-surface elevations. "
                "This is a control estimate, not survey-grade validation."
            ),
        }


def estimate_control_offset(
    values: NDArray[np.floating] | list[float],
    *,
    surface: str,
    max_abs_m: float = 2.0,
    bootstrap_samples: int = 2_000,
    seed: int = 42,
) -> ControlEstimate:
    """Estimate a robust constant offset from paired differences.

    Parameters
    ----------
    values : array-like
        2018-minus-2022 elevation differences on stable surfaces.
    surface : str
        Control-surface label.
    max_abs_m : float
        Initial and final robust trimming threshold.
    bootstrap_samples : int
        Number of bootstrap resamples.
    seed : int
        Random seed.

    Returns
    -------
    ControlEstimate
        Median, spread, and bootstrap interval.

    Raises
    ------
    ValueError
        When no finite values remain or a limit is invalid.
    """
    if max_abs_m <= 0.0:
        raise ValueError("max_abs_m must be positive")
    if bootstrap_samples < 1:
        raise ValueError("bootstrap_samples must be positive")
    array = np.asarray(values, dtype=np.float64)
    array = array[np.isfinite(array)]
    if array.size == 0:
        raise ValueError("no finite control observations")
    median = float(np.median(array))
    retained = array[np.abs(array - median) <= max_abs_m]
    if retained.size == 0:
        raise ValueError("no control observations remain after trimming")
    median = float(np.median(retained))
    mad = float(np.median(np.abs(retained - median)))
    rng = np.random.default_rng(seed)
    size = min(retained.size, 20_000)
    medians = np.empty(bootstrap_samples, dtype=np.float64)
    for index in range(bootstrap_samples):
        medians[index] = float(np.median(rng.choice(retained, size=size, replace=True)))
    low, high = np.percentile(medians, [2.5, 97.5])
    p25, p75 = np.percentile(retained, [25, 75])
    return ControlEstimate(
        surface=surface,
        count=int(retained.size),
        offset_m=median,
        median_abs_deviation_m=mad,
        percentile_25_m=float(p25),
        percentile_75_m=float(p75),
        bootstrap_low_m=float(low),
        bootstrap_high_m=float(high),
        max_abs_m=max_abs_m,
    )


__all__ = ["ControlEstimate", "estimate_control_offset"]
