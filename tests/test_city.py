"""Tests for full-city LiDAR tile rasterisation and mosaic assembly."""

from __future__ import annotations

import json
from pathlib import Path

import laspy
import numpy as np
import pytest

from fresh_urban_forest.city import (
    build_city_mosaic,
    load_city_tile,
    rasterize_las_tile,
    save_city_tile,
)


def _write_test_las(path: Path, *, x_offset: float = 0.0) -> Path:
    """Write a small synthetic classified LAS tile.

    Parameters
    ----------
    path : Path
        Destination path.
    x_offset : float
        Easting offset for the tile.

    Returns
    -------
    Path
        The written path.
    """
    header = laspy.LasHeader(point_format=6, version="1.4")
    header.offsets = np.asarray([0.0, 0.0, 0.0])
    header.scales = np.asarray([0.01, 0.01, 0.01])
    las = laspy.LasData(header)
    # 10 m x 10 m with one return in each 1 m cell.
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    classes: list[int] = []
    for row in range(10):
        for col in range(10):
            x = x_offset + col + 0.5
            y = row + 0.5
            xs.append(x)
            ys.append(y)
            zs.append(1.0)
            classes.append(2)
            if col < 4 and row < 4:
                xs.append(x)
                ys.append(y)
                zs.append(6.0)
                classes.append(5)
            if col == 9 and row == 9:
                xs.append(x)
                ys.append(y)
                zs.append(8.0)
                classes.append(6)
            if col == 0 and row == 9:
                xs.append(x)
                ys.append(y)
                zs.append(0.5)
                classes.append(9)
    las.x = np.asarray(xs)
    las.y = np.asarray(ys)
    las.z = np.asarray(zs)
    las.classification = np.asarray(classes, dtype=np.uint8)
    las.write(path)
    return path


def test_rasterize_las_uses_asprs_classes(tmp_path: Path) -> None:
    """Class 5 is vegetation, class 6 is building, and class 9 is water."""
    path = _write_test_las(tmp_path / "tile.las")
    tile = rasterize_las_tile(path, crs_override="EPSG:3157")
    assert tile.crs == "EPSG:3157"
    assert tile.dem.shape == (10, 10)
    assert np.nanmax(tile.vegetation) == pytest.approx(6.0)
    assert np.nanmax(tile.building) == pytest.approx(8.0)
    assert int(tile.water.sum()) == 1
    assert tile.class_counts == ((2, 100), (5, 16), (6, 1), (9, 1))


def test_city_tile_round_trip(tmp_path: Path) -> None:
    """A rasterised tile survives an NPZ round trip."""
    path = _write_test_las(tmp_path / "tile.las")
    tile = rasterize_las_tile(path, crs_override="EPSG:3157")
    saved = save_city_tile(tile, tmp_path / "tile.npz")
    loaded = load_city_tile(saved)
    assert loaded.crs == tile.crs
    assert loaded.bounds == tile.bounds
    np.testing.assert_allclose(loaded.dem, tile.dem, equal_nan=True)
    np.testing.assert_array_equal(loaded.water, tile.water)


def test_mosaic_clips_to_aoi_and_reports_coverage(tmp_path: Path) -> None:
    """Two adjacent tiles mosaic into one AOI grid."""
    first = rasterize_las_tile(
        _write_test_las(tmp_path / "first.las"),
        tile_id="first",
        crs_override="EPSG:3157",
    )
    second = rasterize_las_tile(
        _write_test_las(tmp_path / "second.las", x_offset=10.0),
        tile_id="second",
        crs_override="EPSG:3157",
    )
    first_path = save_city_tile(first, tmp_path / "first.npz")
    second_path = save_city_tile(second, tmp_path / "second.npz")
    aoi = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[0.0, 0.0], [20.0, 0.0], [20.0, 10.0], [0.0, 10.0], [0.0, 0.0]]
                    ],
                },
            }
        ],
    }
    aoi_path = tmp_path / "aoi.geojson"
    aoi_path.write_text(json.dumps(aoi), encoding="utf-8")
    out_dir = tmp_path / "mosaic"
    summary = build_city_mosaic(
        [first_path, second_path],
        aoi_path=aoi_path,
        out_dir=out_dir,
        aoi_crs="EPSG:3157",
    )
    assert summary.width == 20
    assert summary.height == 10
    assert summary.tile_count == 2
    assert summary.coverage_fraction == pytest.approx(1.0)
    assert (out_dir / "chm.tif").exists()
    assert (out_dir / "manifest.json").exists()
