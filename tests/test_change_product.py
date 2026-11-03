"""Tests for the observed-change product."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from fresh_urban_forest.change_product import build_change_product
from fresh_urban_forest.models import TerrainGrid


def _grid(canopy: np.ndarray) -> TerrainGrid:
    """Build a small terrain grid for change tests."""
    return TerrainGrid(
        crs="EPSG:3157",
        bounds=(0.0, 0.0, 100.0, 100.0),
        width=int(canopy.shape[1]),
        height=int(canopy.shape[0]),
        elevation=np.zeros(canopy.shape, dtype=np.float32),
        canopy_height=canopy.astype(np.float32),
    )


def test_build_change_product_writes_summary_png_and_grid(tmp_path: Path) -> None:
    """The product records gain, loss, stable canopy, and a PNG overlay."""
    earlier = np.zeros((10, 10), dtype=np.float32)
    later = np.zeros((10, 10), dtype=np.float32)
    earlier[:, :3] = 10.0
    later[:, :3] = 10.0
    later[:, 3:5] = 8.0
    later[:, 7:] = 12.0
    earlier[:, 5:7] = 10.0
    path = build_change_product(
        _grid(earlier),
        _grid(later),
        tmp_path,
        threshold_m=2.0,
        earlier_label="2016",
        later_label="2021",
    )
    payload = json.loads(path.read_text())
    assert payload["earlier_label"] == "2016"
    assert payload["later_label"] == "2021"
    assert payload["metrics"]["gain_m2"] == 5000.0
    assert payload["metrics"]["loss_m2"] == 2000.0
    assert payload["metrics"]["stable_m2"] == 3000.0
    assert payload["legend"]
    assert payload["bounds_wgs84"][0] < payload["bounds_wgs84"][2]
    assert payload["valid_bounds_wgs84"][0] < payload["valid_bounds_wgs84"][2]
    assert len(payload["corners_wgs84"]) == 4
    assert (tmp_path / "change.png").read_bytes().startswith(b"\x89PNG")
    assert (tmp_path / "change_grid.npz").exists()


def test_build_change_product_rejects_mismatched_grids(tmp_path: Path) -> None:
    """Mismatched shapes or bounds are refused."""
    first = _grid(np.ones((10, 10), dtype=np.float32))
    second = _grid(np.ones((9, 10), dtype=np.float32))
    with pytest.raises(ValueError, match="shape"):
        build_change_product(first, second, tmp_path)
    no_canopy = TerrainGrid(
        crs="EPSG:3157",
        bounds=(0.0, 0.0, 100.0, 100.0),
        width=10,
        height=10,
        elevation=np.zeros((10, 10), dtype=np.float32),
        canopy_height=None,
    )
    with pytest.raises(ValueError, match="canopy_height"):
        build_change_product(no_canopy, first, tmp_path)
