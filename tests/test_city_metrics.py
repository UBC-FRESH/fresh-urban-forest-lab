"""Tests for city-wide and local-area metrics."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine

from fresh_urban_forest.city_metrics import compute_city_metrics
from fresh_urban_forest.models import TreeRecord


def _write_raster(path: Path, values: np.ndarray, *, dtype: str = "float32") -> Path:
    """Write a small projected GeoTIFF for a test."""
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=values.shape[0],
        width=values.shape[1],
        count=1,
        dtype=dtype,
        crs="EPSG:3157",
        transform=Affine(1.0, 0.0, 0.0, 0.0, -1.0, float(values.shape[0])),
    ) as dataset:
        dataset.write(values.astype(dtype), 1)
    return path


def test_compute_city_metrics_reconciles_city_and_local_areas(tmp_path: Path) -> None:
    """City totals reconcile with two contiguous local areas."""
    chm = np.full((10, 20), 5.0, dtype=np.float32)
    chm_path = _write_raster(tmp_path / "chm.tif", chm)
    mask_path = _write_raster(
        tmp_path / "mask.tif", np.zeros((10, 20), dtype=np.uint8), dtype="uint8"
    )
    aoi = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "West"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0]]
                    ],
                },
            },
            {
                "type": "Feature",
                "properties": {"name": "East"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[10.0, 0.0], [20.0, 0.0], [20.0, 10.0], [10.0, 10.0], [10.0, 0.0]]
                    ],
                },
            },
        ],
    }
    aoi_path = tmp_path / "aoi.geojson"
    aoi_path.write_text(json.dumps(aoi), encoding="utf-8")
    trees = (
        TreeRecord(
            tree_id="a",
            lon=0.0,
            lat=0.0,
            species="Acer rubrum",
            dbh_cm=20.0,
            height_m=10.0,
            crown_width_m=4.0,
            x_m=5.0,
            y_m=5.0,
            attributes={"local_area": "West"},
        ),
        TreeRecord(
            tree_id="b",
            lon=0.0,
            lat=0.0,
            species="Acer rubrum",
            dbh_cm=20.0,
            height_m=10.0,
            crown_width_m=4.0,
            x_m=15.0,
            y_m=5.0,
            attributes={"local_area": "East"},
        ),
    )
    payload = compute_city_metrics(
        trees,
        chm_path=chm_path,
        building_mask_path=mask_path,
        water_mask_path=mask_path,
        aoi_path=aoi_path,
        out_dir=tmp_path / "out",
        aoi_crs="EPSG:3157",
    )
    city = payload["city"]
    assert isinstance(city, dict)
    assert city["tree_count"] == 2
    assert city["canopy_cover_pct"] == 100.0
    assert city["canopy_volume_m3"] == 1000.0
    local_areas = payload["local_areas"]
    assert isinstance(local_areas, list)
    assert len(local_areas) == 2
    assert payload["tree_count_assigned"] == 2
    assert (tmp_path / "out" / "city_metrics.json").exists()
