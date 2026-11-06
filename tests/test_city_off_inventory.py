"""Tests for the full-city off-inventory helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio

from fresh_urban_forest.city_off_inventory import detect_city_trees, match_inventory
from fresh_urban_forest.itd import DetectedTree
from fresh_urban_forest.models import TreeRecord


def test_match_inventory_is_one_to_one() -> None:
    """A detected crown can consume only one public tree."""
    detected = (
        DetectedTree("d1", 0, 0, 10.0, 3.0, 28.3, 0.0, 0.0, -123.0, 49.0),
        DetectedTree("d2", 0, 0, 10.0, 3.0, 28.3, 1.0, 0.0, -123.0, 49.0),
    )
    trees = (
        TreeRecord("t1", -123.0, 49.0, height_m=10.0, x_m=0.0, y_m=0.0),
        TreeRecord("t2", -123.0, 49.0, height_m=10.0, x_m=0.5, y_m=0.0),
    )
    result = match_inventory(detected, trees, max_distance_m=5.0)
    assert result.matched == 2
    assert result.unmatched_detected == ()
    assert result.unmatched_inventory == ()


def test_detect_city_trees_finds_a_synthetic_peak(tmp_path: Path) -> None:
    """The tiled detector returns at least one crown from a small CHM."""
    values = np.zeros((20, 20), dtype=np.float32)
    values[8:12, 8:12] = 12.0
    path = tmp_path / "chm.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=20,
        width=20,
        count=1,
        dtype="float32",
        crs="EPSG:3157",
        transform=rasterio.transform.from_origin(0.0, 20.0, 1.0, 1.0),
    ) as dataset:
        dataset.write(values, 1)
    trees = detect_city_trees(path, resolution_m=1.0, tile_m=1000.0)
    assert len(trees) >= 1
    assert trees[0].tree_id.startswith("city-")


def test_detect_city_trees_uses_source_cell_size(tmp_path: Path) -> None:
    """A 2 m CHM is not treated as 1 m when resolution is requested in metres."""
    values = np.zeros((20, 20), dtype=np.float32)
    values[5, 15] = 14.0
    path = tmp_path / "chm_2m.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=20,
        width=20,
        count=1,
        dtype="float32",
        crs="EPSG:3157",
        transform=rasterio.transform.from_origin(0.0, 40.0, 2.0, 2.0),
    ) as dataset:
        dataset.write(values, 1)
    trees = detect_city_trees(path, resolution_m=1.0, tile_m=1000.0)
    assert trees
    assert trees[0].x > 20.0
