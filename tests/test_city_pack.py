"""Tests for assembling the portable city dataset."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from fresh_urban_forest.city_pack import build_city_pack
from fresh_urban_forest.terrain import unproject_xy
from tests.fixtures import BOUNDS, CRS, make_raster, make_trees


def _building_geojson(path: Path) -> Path:
    """Write one small building footprint around local (25, 25)."""
    corners = [
        unproject_xy(25.0, 25.0, CRS),
        unproject_xy(35.0, 25.0, CRS),
        unproject_xy(35.0, 35.0, CRS),
        unproject_xy(25.0, 35.0, CRS),
        unproject_xy(25.0, 25.0, CRS),
    ]
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"BLDG_UID": "b1", "NAME": "Test building"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[lon, lat] for lon, lat in corners]],
                },
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_build_city_pack_writes_dataset_and_metrics(tmp_path: Path) -> None:
    """A small city pack is written with the expected files and sample limits."""
    dem = make_raster(tmp_path / "dem.tif", np.zeros((100, 100), dtype=np.float32))
    chm = make_raster(tmp_path / "chm.tif", np.full((100, 100), 5.0, dtype=np.float32))
    height = make_raster(tmp_path / "height.tif", np.full((100, 100), 12.0, dtype=np.float32))
    buildings = _building_geojson(tmp_path / "buildings.geojson")
    city_metrics = {
        "city": {
            "tree_count": 12,
            "native_fraction": 0.5,
            "canopy_cover_pct": 50.0,
            "canopy_volume_m3": 1000.0,
            "tree_height_mean_m": 10.0,
            "tree_height_p50_m": 10.0,
            "tree_height_p95_m": 20.0,
            "carbon_kg": 5000.0,
            "shannon_index": 1.2,
        }
    }
    boundary = (
        unproject_xy(BOUNDS[0], BOUNDS[1], CRS),
        unproject_xy(BOUNDS[2], BOUNDS[1], CRS),
        unproject_xy(BOUNDS[2], BOUNDS[3], CRS),
        unproject_xy(BOUNDS[0], BOUNDS[3], CRS),
        unproject_xy(BOUNDS[0], BOUNDS[1], CRS),
    )
    out = tmp_path / "city"
    dataset = build_city_pack(
        trees=tuple(make_trees(12)),
        city_metrics=city_metrics,
        inventory_summary={},
        dem=dem,
        chm=chm,
        building_footprints=buildings,
        building_height=height,
        boundary=boundary,
        sources=(),
        out_dir=out,
        max_trees=12,
        max_buildings=10,
        terrain_max_size=40,
    )
    assert dataset.manifest.tree_count == 12
    assert (out / "manifest.json").exists()
    assert (out / "trees.json").exists()
    assert (out / "city_metrics.json").exists()
    assert (out / "inventory_summary.json").exists()
    assert (out / "buildings.geojson").exists()
