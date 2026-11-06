"""Independent CHM-derived crown-shape features.

These features are computed from the canopy-height raster around a point, not from the
inventory's species-derived height/crown fields. They are used to test whether image
probabilities and LiDAR crown shape add independent signal.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from fresh_urban_forest.terrain import RasterData

FEATURE_NAMES: tuple[str, ...] = (
    "chm_max_m",
    "chm_center_m",
    "canopy_fraction",
    "crown_area_m2",
    "height_p90_m",
    "height_std_m",
    "center_to_max_ratio",
)


@dataclass(frozen=True, slots=True)
class CrownFeatures:
    """CHM-derived features for one location.

    Attributes
    ----------
    values : tuple of float
        Feature values in :data:`FEATURE_NAMES` order.
    canopy_height_m : float
        Maximum canopy height in the patch.
    crown_area_m2 : float
        Area of cells above the 2 m canopy threshold.
    """

    values: tuple[float, ...]
    canopy_height_m: float
    crown_area_m2: float


def crown_features(
    chm: RasterData,
    x: float,
    y: float,
    *,
    patch_radius_m: float = 15.0,
) -> CrownFeatures:
    """Calculate CHM crown-shape features around a projected point.

    Parameters
    ----------
    chm : RasterData
        Canopy-height raster.
    x, y : float
        Projected coordinates in the CHM CRS.
    patch_radius_m : float
        Patch radius in metres.

    Returns
    -------
    CrownFeatures
        Features and the maximum canopy height.
    """
    resolution = math.sqrt(chm.cell_area_m2)
    col = int((x - chm.bounds[0]) / resolution)
    row = int((chm.bounds[3] - y) / resolution)
    radius = max(1, math.ceil(patch_radius_m / resolution))
    row0 = max(0, row - radius)
    row1 = min(chm.array.shape[0], row + radius + 1)
    col0 = max(0, col - radius)
    col1 = min(chm.array.shape[1], col + radius + 1)
    if row1 <= row0 or col1 <= col0:
        return CrownFeatures((0.0,) * len(FEATURE_NAMES), 0.0, 0.0)
    patch = np.asarray(chm.array[row0:row1, col0:col1], dtype=np.float64)
    finite = np.isfinite(patch)
    canopy = np.where(finite, patch, 0.0)
    canopy = np.clip(canopy, 0.0, None)
    threshold = 2.0
    canopy_mask = canopy >= threshold
    height_max = float(np.max(canopy)) if canopy.size else 0.0
    center_index = (min(row, row1 - 1) - row0, min(col, col1 - 1) - col0)
    center_height = float(canopy[center_index]) if canopy.size else 0.0
    fraction = float(np.mean(canopy_mask)) if canopy.size else 0.0
    area = float(np.count_nonzero(canopy_mask) * chm.cell_area_m2)
    heights = canopy[canopy_mask]
    p90 = float(np.percentile(heights, 90)) if heights.size else 0.0
    std = float(np.std(heights)) if heights.size else 0.0
    ratio = center_height / height_max if height_max > 0 else 0.0
    values = (
        height_max,
        center_height,
        fraction,
        area,
        p90,
        std,
        ratio,
    )
    return CrownFeatures(tuple(float(value) for value in values), height_max, area)
