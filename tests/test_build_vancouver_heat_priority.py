"""Tests for the Vancouver shade-equity build script."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin

from build_vancouver_heat_priority import (
    build_product,
    load_census,
    load_rasters,
    parse_args,
    raster_shape,
    time_samples,
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


def _write_profiles(directory: Path) -> None:
    """Write the nine minimal Census Profile CSV files."""
    rows = [
        ("d1", "500", "50", "400", "50", "80000", "500", "50", "4"),
        ("d2", "500", "100", "350", "50", "40000", "500", "250", "12"),
    ]
    specs = (
        ("1", "1", 1),
        ("9", "1", 2),
        ("13", "1", 3),
        ("24", "1", 4),
        ("113", "1", 5),
        ("1669", "1", 6),
        ("1670", "1", 7),
        ("2230", "4", 8),
    )
    header = "DATAFLOW,FREQ,TIME_PERIOD,REF_AREA,GENDER,CHARACTERISTIC,STATISTIC,OBS_VALUE\n"
    for characteristic, statistic, column in specs:
        lines = [header.rstrip("\n")]
        for row in rows:
            lines.append(
                f"STC_CP:DF_DA(1.3),A5,2021,{row[0]},1,{characteristic},{statistic},{row[column]}"
            )
        (directory / f"cp_{characteristic}.{statistic}.csv").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )


def _make_inputs(tmp_path: Path) -> tuple[Path, Path]:
    """Create a tiny city dataset and census directory."""
    root = tmp_path / "city"
    census = tmp_path / "census"
    root.mkdir()
    census.mkdir()
    shape = (40, 40)
    _write_raster(root / "dem.tif", np.zeros(shape), "float32")
    _write_raster(root / "chm.tif", np.full(shape, 8.0), "float32")
    _write_raster(root / "building_height.tif", np.zeros(shape), "float32")
    _write_raster(root / "building_mask.tif", np.zeros(shape), "uint8")
    _write_raster(root / "water_mask.tif", np.zeros(shape), "uint8")
    (root / "terrain.json").write_text(
        json.dumps({"bounds": list(BOUNDS), "crs": CRS, "width": 40, "height": 40}),
        encoding="utf-8",
    )
    (root / "manifest.json").write_text(json.dumps({"dataset_id": "test-city"}), encoding="utf-8")
    _write_profiles(census)
    transformer = Transformer.from_crs(CRS, "EPSG:4326", always_xy=True)

    def _ring(left: float, bottom: float, right: float, top: float) -> list[list[float]]:
        corners = [
            (left, bottom),
            (left, top),
            (right, top),
            (right, bottom),
            (left, bottom),
        ]
        return [list(transformer.transform(x, y)) for x, y in corners]

    geometry = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"DGUID": "d1"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [_ring(493000.0, 5455000.0, 493200.0, 5455400.0)],
                },
            },
            {
                "type": "Feature",
                "properties": {"DGUID": "d2"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [_ring(493200.0, 5455000.0, 493400.0, 5455400.0)],
                },
            },
        ],
    }
    (census / "da_geometry_vancouver.geojson").write_text(json.dumps(geometry), encoding="utf-8")
    return root, census


def test_parse_args_defaults() -> None:
    """The script has a local default data path."""
    args = parse_args([])
    assert args.resolution == 5.0
    assert args.cell_size == 400.0
    assert args.root.name == "vancouver_2022"


def test_raster_shape_and_time_samples() -> None:
    """The grid shape and solar samples are deterministic."""
    assert raster_shape((0.0, 0.0, 400.0, 400.0), 10.0) == (40, 40)
    assert len(time_samples(2022)) == 8
    assert time_samples(2022)[0].hour == 10
    with pytest.raises(ValueError, match="positive"):
        raster_shape((0.0, 0.0, 0.0, 1.0), 10.0)


def test_load_rasters_and_census(tmp_path: Path) -> None:
    """Rasters and Census profiles load from the expected layout."""
    root, census = _make_inputs(tmp_path)
    dem, canopy, building, building_mask, water_mask, bounds, crs = load_rasters(root, 10.0)
    assert dem.shape == (40, 40)
    assert float(np.max(canopy)) == pytest.approx(8.0)
    assert float(np.max(building)) == 0.0
    assert not building_mask.any()
    assert not water_mask.any()
    assert bounds == BOUNDS
    assert crs == CRS
    frame, summary = load_census(census)
    assert len(frame) == 2
    assert summary["areas_with_score"] == 2


def test_load_rasters_rejects_missing_terrain(tmp_path: Path) -> None:
    """A missing terrain metadata file is an explicit error."""
    with pytest.raises(FileNotFoundError):
        load_rasters(tmp_path, 10.0)


def test_build_product_writes_products(tmp_path: Path) -> None:
    """The full small build writes JSON, GeoJSON, PNG, and metadata."""
    root, census = _make_inputs(tmp_path)
    out = tmp_path / "out"
    result = build_product(
        root=root,
        census_dir=census,
        out_dir=out,
        resolution=10.0,
        cell_size=400.0,
        year=2022,
    )
    assert result["dataset_id"] == "test-city"
    assert result["cell_count"] == 1
    assert (out / "heat_priority.json").exists()
    assert (out / "heat_priority.geojson").exists()
    assert (out / "heat_priority.png").exists()
    assert (out / "heat_priority_meta.json").exists()
    payload = json.loads((out / "heat_priority.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["dataset_id"] == "test-city"
    assert payload["cells"][0]["priority_class"] in {"1A", "1B", "2A", "2B", "3A", "3B", "4A", "4B"}
