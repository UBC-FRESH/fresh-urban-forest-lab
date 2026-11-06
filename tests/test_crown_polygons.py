"""Tests for candidate crown polygon extraction."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from build_off_inventory_crown_polygons import main
from fresh_urban_forest.terrain import unproject_xy


def test_crown_polygon_command_finds_a_candidate(tmp_path: Path) -> None:
    """A synthetic CHM blob produces a candidate polygon."""
    chm = tmp_path / "chm.tif"
    values = np.zeros((40, 40), dtype=np.float32)
    values[18:24, 18:24] = 12.0
    with rasterio.open(
        chm,
        "w",
        driver="GTiff",
        height=40,
        width=40,
        count=1,
        dtype="float32",
        crs="EPSG:3157",
        transform=from_origin(0.0, 40.0, 1.0, 1.0),
    ) as dataset:
        dataset.write(values, 1)
    lon, lat = unproject_xy(21.0, 19.0, "EPSG:3157")
    candidates = tmp_path / "candidates.geojson.gz"
    with gzip.open(candidates, "wt", encoding="utf-8") as handle:
        json.dump(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [lon, lat]},
                        "properties": {
                            "candidate_id": "c1",
                            "height_m": 12.0,
                            "confidence": 0.8,
                            "land_class": "likely private parcel",
                            "support_class": "high",
                        },
                    }
                ],
            },
            handle,
        )
    output = tmp_path / "polygons.geojson.gz"
    assert main(["--chm", str(chm), "--candidates", str(candidates), "--output", str(output)]) == 0
    with gzip.open(output, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert payload["features"]
    assert payload["features"][0]["properties"]["candidate_id"] == "c1"
    assert payload["features"][0]["geometry"]["type"] == "Polygon"
