"""Tests for the Vancouver heat-equity build script."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from build_vancouver_heat_equity import (
    build_product,
    load_priority,
    load_scene_manifest,
    parse_args,
    read_mask,
    target_shape,
)

CRS = "EPSG:3157"
BOUNDS = (493_000.0, 5_455_000.0, 493_300.0, 5_455_300.0)


def _write_raster(path: Path, values: np.ndarray, dtype: str, nodata: int | None = None) -> None:
    """Write a tiny GeoTIFF."""
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
        transform=from_origin(BOUNDS[0], BOUNDS[3], 30.0, 30.0),
        nodata=nodata,
    ) as dataset:
        dataset.write(values.astype(dtype), 1)


def _make_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create P30 masks, a Landsat scene, and a P38 product."""
    root = tmp_path / "city"
    landsat = tmp_path / "landsat"
    root.mkdir()
    landsat.mkdir()
    shape = (10, 10)
    _write_raster(root / "building_mask.tif", np.zeros(shape), "uint8", 255)
    _write_raster(root / "water_mask.tif", np.zeros(shape), "uint8", 255)
    scene = landsat / "SCENE"
    scene.mkdir()
    st_path = scene / "ST_B10.TIF"
    qa_path = scene / "QA_PIXEL.TIF"
    _write_raster(st_path, np.full(shape, 42000, dtype=np.uint16), "uint16", 0)
    qa = np.full(shape, 1 << 6, dtype=np.uint16)
    qa[2, 2] = (1 << 6) | (1 << 3)
    _write_raster(qa_path, qa, "uint16", 0)
    manifest = [
        {
            "id": "SCENE",
            "datetime": "2022-07-26T19:07:59Z",
            "cloud_cover": 0.2,
            "files": {"lwir11": str(st_path), "qa_pixel": str(qa_path)},
        }
    ]
    (landsat / "download_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    heat = tmp_path / "heat_priority.json"
    heat.write_text(
        json.dumps(
            {
                "metadata": {"bounds": list(BOUNDS), "crs": CRS},
                "cells": [
                    {
                        "cell_id": "r00c00",
                        "equity_score": 0.8,
                        "shade_deficit": 0.7,
                        "priority_class": "1A",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return root, landsat, heat


def test_parse_args_and_target_shape() -> None:
    """The script defaults and grid shape are deterministic."""
    args = parse_args([])
    assert args.resolution == 30.0
    assert target_shape((0.0, 0.0, 300.0, 300.0), 30.0) == (10, 10)
    with pytest.raises(ValueError, match="positive"):
        target_shape((0.0, 0.0, 0.0, 1.0), 30.0)


def test_read_mask_handles_nodata(tmp_path: Path) -> None:
    """Nodata pixels are excluded from the mask."""
    path = tmp_path / "mask.tif"
    values = np.array([[1, 0], [255, 1]], dtype=np.uint8)
    _write_raster(path, values, "uint8", 255)
    mask = read_mask(path, (2, 2))
    assert mask.tolist() == [[True, False], [False, True]]


def test_load_priority_and_manifest(tmp_path: Path) -> None:
    """The P38 cells and scene manifest load from the expected layout."""
    _, landsat, heat = _make_inputs(tmp_path)
    cells, metadata = load_priority(heat)
    assert set(cells) == {"r00c00"}
    assert metadata["crs"] == CRS
    manifest = load_scene_manifest(landsat)
    assert manifest[0]["id"] == "SCENE"


def test_loaders_require_files(tmp_path: Path) -> None:
    """Missing P38 or manifest files are explicit errors."""
    with pytest.raises(FileNotFoundError):
        load_priority(tmp_path / "missing.json")
    with pytest.raises(FileNotFoundError):
        load_scene_manifest(tmp_path)


def test_build_product_writes_products(tmp_path: Path) -> None:
    """The small build writes JSON, GeoJSON, PNG, and metadata."""
    root, landsat, heat = _make_inputs(tmp_path)
    out = tmp_path / "out"
    result = build_product(
        root=root,
        landsat_dir=landsat,
        heat_priority=heat,
        out_dir=out,
        resolution=30.0,
        cell_size=400.0,
    )
    assert cast("int", result["cell_count"]) == 1
    assert cast("int", result["scene_count"]) == 1
    assert (out / "heat_equity.json").exists()
    assert (out / "heat_equity.geojson").exists()
    assert (out / "heat_equity.png").exists()
    assert (out / "heat_equity_meta.json").exists()
    payload = json.loads((out / "heat_equity.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "fresh-urban-forest.heat-equity.v1"
    assert payload["cells"][0]["cell_id"] == "r00c00"
