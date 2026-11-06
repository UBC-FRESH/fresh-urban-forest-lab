"""Tests for independent CHM crown features."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from fresh_urban_forest.crown_features import FEATURE_NAMES, crown_features
from tests.fixtures import make_raster


def test_crown_features_measure_a_canopy_patch(tmp_path: Path) -> None:
    """A synthetic canopy patch produces finite CHM features."""
    values = np.zeros((40, 40), dtype=np.float32)
    values[15:25, 15:25] = 12.0
    chm = make_raster(tmp_path / "chm.tif", values)
    features = crown_features(chm, 50.0, 50.0, patch_radius_m=6.0)
    assert len(features.values) == len(FEATURE_NAMES)
    assert features.canopy_height_m == 12.0
    assert features.crown_area_m2 > 0
