"""Tests for the citywide 2018-2022 change build."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import laspy
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from build_vancouver_citywide_change import (
    build_change,
    grid_shape,
    parse_args,
    read_later,
    tile_canopy,
    tile_surfaces,
)

CRS = "EPSG:3157"
BOUNDS = (0.0, 0.0, 2.0, 2.0)


def _write_las_zip(path: Path) -> None:
    """Write a ZIP containing a tiny LAS."""
    las = laspy.create(point_format=3, file_version="1.2")
    las.x = np.array([0.1, 0.1, 1.1])
    las.y = np.array([1.9, 1.9, 1.9])
    las.z = np.array([0.0, 5.0, 0.5])
    las.classification = np.array([2, 5, 2], dtype=np.uint8)
    las_path = path.with_suffix(".las")
    las.write(las_path)
    with zipfile.ZipFile(path, "w") as archive:
        archive.write(las_path, las_path.name)
    las_path.unlink()


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


def test_parse_args_and_grid_shape() -> None:
    """The default resolution and grid shape are deterministic."""
    args = parse_args([])
    assert args.resolution == 5.0
    assert args.stride == 32
    assert grid_shape((0.0, 0.0, 10.0, 10.0), 5.0) == (2, 2)
    with pytest.raises(ValueError, match="positive"):
        grid_shape((0.0, 0.0, 0.0, 1.0), 5.0)


def test_tile_surfaces_reads_zip_and_classes(tmp_path: Path) -> None:
    """The ZIP reader builds a positive canopy height."""
    zip_path = tmp_path / "tile.zip"
    _write_las_zip(zip_path)
    ground, canopy, valid, counters = tile_surfaces(
        [zip_path], bounds=BOUNDS, shape=(2, 2), stride=1
    )
    assert valid[0, 0]
    assert ground[0, 0] == pytest.approx(0.0)
    assert canopy[0, 0] == pytest.approx(5.0)
    assert counters["tiles"] == 1
    assert counters["ground"] >= 1


def test_tile_canopy_reads_zip(tmp_path: Path) -> None:
    """The canopy-only path returns the vegetation maximum."""
    zip_path = tmp_path / "tile.zip"
    _write_las_zip(zip_path)
    canopy, counters = tile_canopy([zip_path], bounds=BOUNDS, shape=(2, 2), stride=1)
    assert canopy[0, 0] == pytest.approx(5.0)
    assert counters["canopy"] >= 1


def test_tile_surfaces_rejects_bad_stride(tmp_path: Path) -> None:
    """A non-positive stride is rejected."""
    with pytest.raises(ValueError, match="stride"):
        tile_surfaces([], bounds=BOUNDS, shape=(2, 2), stride=0)


def test_read_later_and_build_change(tmp_path: Path) -> None:
    """The later raster and full change build produce a summary."""
    later = tmp_path / "later"
    later.mkdir()
    _write_raster(later / "chm.tif", np.full((2, 2), 4.0))
    _write_raster(later / "dem.tif", np.zeros((2, 2)))
    window = read_later(later / "chm.tif", BOUNDS, (2, 2))
    assert window.shape == (2, 2)
    las_dir = tmp_path / "las"
    las_dir.mkdir()
    _write_las_zip(las_dir / "tile.zip")
    out = tmp_path / "out"
    path = build_change(
        las_dir=las_dir,
        later_root=later,
        out_dir=out,
        bounds=BOUNDS,
        resolution=1.0,
        stride=1,
    )
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "net_m2" in payload["metrics"]
    process = json.loads((out / "change_process.json").read_text(encoding="utf-8"))
    assert process["stride"] == 1
