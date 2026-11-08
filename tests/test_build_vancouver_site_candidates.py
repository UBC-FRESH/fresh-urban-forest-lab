"""Tests for the Vancouver candidate-site build script."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import cast

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin

from build_vancouver_site_candidates import (
    build_product,
    load_action_cells,
    parse_args,
)

CRS = "EPSG:3157"
BOUNDS = (493_000.0, 5_455_000.0, 493_400.0, 5_455_400.0)


def _write_raster(path: Path, values: np.ndarray, dtype: str) -> None:
    """Write a one-band GeoTIFF fixture."""
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=values.shape[0],
        width=values.shape[1],
        count=1,
        dtype=dtype,
        crs=CRS,
        transform=from_origin(BOUNDS[0], BOUNDS[3], 10.0, 10.0),
        nodata=0 if dtype == "uint8" else np.nan,
    ) as dataset:
        dataset.write(values.astype(dtype), 1)


def _make_inputs(tmp_path: Path) -> tuple[Path, Path]:
    """Create a tiny city dataset, roads, and action product."""
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
    action_path = root / "canopy_action.json"
    action_path.write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "cell_id": "r00c00",
                        "action_class": "plant_cool",
                        "action_label": "plant + cool",
                        "opportunity_tier": "high",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return root, action_path


def test_parse_args_and_load_action_cells(tmp_path: Path) -> None:
    """Defaults and action loading are explicit."""
    args = parse_args([])
    assert args.resolution == 5.0
    assert args.max_sites_per_cell > 0
    root, action_path = _make_inputs(tmp_path)
    actions = load_action_cells(action_path)
    assert actions["r00c00"]["action_class"] == "plant_cool"
    assert load_action_cells(root / "canopy_action.json") == actions


def test_build_product_writes_candidate_files(tmp_path: Path) -> None:
    """The small build writes deterministic candidate JSON and GeoJSON."""
    root, action_path = _make_inputs(tmp_path)
    out = tmp_path / "out"
    result = build_product(
        root=root,
        action=action_path,
        out_dir=out,
        resolution=10.0,
        cell_size=400.0,
        max_sites=100,
    )
    assert cast("int", result["candidate_count"]) > 0
    paths = cast("dict[str, str]", result["paths"])
    payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert payload["schema_version"] == "fresh-urban-forest.site-candidates.v1"
    assert payload["metadata"]["candidate_count"] == len(payload["sites"])
    assert all("owner" not in site and "address" not in site for site in payload["sites"])
