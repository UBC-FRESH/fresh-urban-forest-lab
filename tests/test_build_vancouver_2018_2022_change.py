"""Tests for the downtown 2018→2022 change build."""

from __future__ import annotations

import json
from pathlib import Path

import laspy
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from build_vancouver_2018_2022_change import (
    build_change,
    grid_indices,
    las_surfaces,
    parse_args,
    raster_window,
)

CRS = "EPSG:3157"
BOUNDS = (0.0, 0.0, 2.0, 2.0)


def _write_las(path: Path) -> None:
    """Write a tiny LAS with ground and canopy points."""
    las = laspy.create(point_format=3, file_version="1.2")
    las.x = np.array([0.1, 0.1, 1.1])
    las.y = np.array([1.9, 1.9, 1.9])
    las.z = np.array([0.0, 5.0, 0.5])
    las.classification = np.array([2, 5, 2], dtype=np.uint8)
    las.write(path)


def _write_raster(path: Path, values: np.ndarray) -> None:
    """Write a tiny 1 m GeoTIFF."""
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=values.shape[0],
        width=values.shape[1],
        count=1,
        dtype="float32",
        crs=CRS,
        transform=from_origin(BOUNDS[0], BOUNDS[3], 1.0, 1.0),
        nodata=np.nan,
    ) as dataset:
        dataset.write(values.astype(np.float32), 1)


def test_parse_args_and_grid_indices() -> None:
    """The default resolution and coordinate mapping are deterministic."""
    args = parse_args([])
    assert args.resolution == 1.0
    rows, cols = grid_indices(
        np.array([0.1, 1.9]),
        np.array([1.9, 0.1]),
        bounds=BOUNDS,
        shape=(2, 2),
    )
    assert rows.tolist() == [0, 1]
    assert cols.tolist() == [0, 1]


def test_las_surfaces_builds_canopy_height(tmp_path: Path) -> None:
    """Ground and vegetation classes produce a positive CHM."""
    path = tmp_path / "tile.las"
    _write_las(path)
    ground, canopy, valid = las_surfaces([path], bounds=BOUNDS, shape=(2, 2))
    assert valid[0, 0]
    assert ground[0, 0] == pytest.approx(0.0)
    assert canopy[0, 0] == pytest.approx(5.0)
    assert canopy[1, 1] == pytest.approx(0.0)


def test_las_surfaces_rejects_no_ground(tmp_path: Path) -> None:
    """A cloud with no ground point fails explicitly."""
    path = tmp_path / "tile.las"
    las = laspy.create(point_format=3, file_version="1.2")
    las.x = np.array([0.1])
    las.y = np.array([1.9])
    las.z = np.array([1.0])
    las.classification = np.array([5], dtype=np.uint8)
    las.write(path)
    with pytest.raises(ValueError, match="no ground"):
        las_surfaces([path], bounds=BOUNDS, shape=(2, 2))


def test_raster_window_and_build_change(tmp_path: Path) -> None:
    """The raster window and end-to-end change build produce a summary."""
    later = tmp_path / "later"
    later.mkdir()
    _write_raster(later / "chm.tif", np.full((2, 2), 4.0))
    _write_raster(later / "dem.tif", np.zeros((2, 2)))
    window = raster_window(later / "chm.tif", bounds=BOUNDS, shape=(2, 2))
    assert window.shape == (2, 2)
    las_dir = tmp_path / "las"
    las_dir.mkdir()
    _write_las(las_dir / "tile.las")
    out = tmp_path / "out"
    path = build_change(
        las_dir=las_dir,
        later_root=later,
        out_dir=out,
        bounds=BOUNDS,
        resolution=1.0,
    )
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["threshold_m"] == 2.0
    assert "net_m2" in payload["metrics"]
