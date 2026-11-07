"""Tests for the Vancouver planting-opportunity build script."""

from __future__ import annotations

import gzip
import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import numpy as np
import pytest
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin

from build_vancouver_planting_opportunity import (
    build_product,
    load_priority,
    load_rasters,
    load_roads,
    parse_args,
    raster_shape,
    road_masks,
)

CRS = "EPSG:3157"
BOUNDS = (493_000.0, 5_455_000.0, 493_400.0, 5_455_400.0)


def _write_raster(path: Path, values: np.ndarray, dtype: str) -> None:
    """Write a one-band GeoTIFF fixture."""
    height, width = values.shape
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype=dtype,
        crs=CRS,
        transform=from_origin(BOUNDS[0], BOUNDS[3], 10.0, 10.0),
        nodata=0 if dtype == "uint8" else np.nan,
    ) as dataset:
        dataset.write(values.astype(dtype), 1)


def _make_inputs(tmp_path: Path) -> tuple[Path, Path]:
    """Create a tiny city dataset and P38 product."""
    root = tmp_path / "city"
    root.mkdir()
    shape = (40, 40)
    _write_raster(root / "dem.tif", np.zeros(shape), "float32")
    canopy = np.zeros(shape, dtype=np.float32)
    canopy[10:20, 10:20] = 10.0
    _write_raster(root / "chm.tif", canopy, "float32")
    _write_raster(root / "building_mask.tif", np.zeros(shape), "uint8")
    _write_raster(root / "water_mask.tif", np.zeros(shape), "uint8")
    (root / "terrain.json").write_text(
        json.dumps({"bounds": list(BOUNDS), "crs": CRS, "width": 40, "height": 40}),
        encoding="utf-8",
    )
    transformer = Transformer.from_crs(CRS, "EPSG:4326", always_xy=True)
    start = transformer.transform(493_000.0, 5_455_000.0)
    end = transformer.transform(493_400.0, 5_455_400.0)
    roads = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"highway": "residential"},
                "geometry": {"type": "LineString", "coordinates": [list(start), list(end)]},
            }
        ],
    }
    with gzip.open(root / "roads.geojson.gz", "wt", encoding="utf-8") as handle:
        json.dump(roads, handle)
    priority_path = tmp_path / "heat_priority.json"
    priority_path.write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "cell_id": f"r{row:02d}c{col:02d}",
                        "shade_deficit": 0.8 if col == 0 else 0.3,
                        "equity_score": 0.9 if row == 0 else 0.2,
                        "priority_class": "1A" if row == 0 and col == 0 else "4B",
                    }
                    for row in range(2)
                    for col in range(2)
                ]
            }
        ),
        encoding="utf-8",
    )
    return root, priority_path


def test_parse_args_and_raster_shape() -> None:
    """The script defaults and grid shape are deterministic."""
    args = parse_args([])
    assert args.resolution == 5.0
    assert args.gap_distance == 15.0
    assert raster_shape((0.0, 0.0, 400.0, 400.0), 10.0) == (40, 40)
    with pytest.raises(ValueError, match="positive"):
        raster_shape((0.0, 0.0, 0.0, 1.0), 10.0)


def test_load_rasters_roads_and_priority(tmp_path: Path) -> None:
    """The expected dataset layout loads rasters, roads, and P38 cells."""
    root, priority_path = _make_inputs(tmp_path)
    dem, canopy, building, water, bounds, crs = load_rasters(root, 10.0)
    assert dem.shape == (40, 40)
    assert float(np.max(canopy)) == pytest.approx(10.0)
    assert not building.any()
    assert not water.any()
    assert bounds == BOUNDS
    assert crs == CRS
    roads = load_roads(root / "roads.geojson.gz", crs)
    assert len(roads) == 1
    surface, centre = road_masks(roads, bounds=bounds, shape=dem.shape)
    assert surface.any()
    assert centre.any()
    priority = load_priority(priority_path)
    assert set(priority) == {"r00c00", "r00c01", "r01c00", "r01c01"}


def test_load_rasters_requires_terrain(tmp_path: Path) -> None:
    """A missing terrain metadata file is an explicit error."""
    with pytest.raises(FileNotFoundError):
        load_rasters(tmp_path, 10.0)


def test_load_roads_requires_file(tmp_path: Path) -> None:
    """A missing road file is an explicit error."""
    with pytest.raises(FileNotFoundError):
        load_roads(tmp_path / "missing.geojson.gz", CRS)


def test_load_priority_requires_file(tmp_path: Path) -> None:
    """A missing P38 product is an explicit error."""
    with pytest.raises(FileNotFoundError):
        load_priority(tmp_path / "missing.json")


def test_build_product_writes_products(tmp_path: Path) -> None:
    """The small build writes JSON, GeoJSON, PNG, and metadata."""
    root, priority_path = _make_inputs(tmp_path)
    out = tmp_path / "out"
    result = build_product(
        root=root,
        heat_priority=priority_path,
        out_dir=out,
        resolution=10.0,
        cell_size=200.0,
    )
    assert cast("int", result["cell_count"]) > 0
    gap_summary = cast("Mapping[str, object]", result["gap_summary"])
    assert cast("float", gap_summary["gap_m2"]) > 0.0
    assert (out / "planting_opportunity.json").exists()
    assert (out / "planting_opportunity.geojson").exists()
    assert (out / "planting_opportunity.png").exists()
    assert (out / "planting_opportunity_meta.json").exists()
    payload = json.loads((out / "planting_opportunity.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "fresh-urban-forest.planting-opportunity.v1"
    assert payload["cells"][0]["opportunity_tier"] in {"high", "medium", "low", "none"}
