"""Integration tests for city off-inventory land context and candidate output."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from shapely.geometry import LineString, box

from fresh_urban_forest.city_off_inventory import (
    CityMatch,
    build_city_candidates,
    classify_land_context,
    write_city_candidates,
)
from fresh_urban_forest.itd import DetectedTree
from fresh_urban_forest.off_inventory import OffInventoryCandidate


def test_classify_land_context_labels_proxy_classes(tmp_path: Path) -> None:
    """Park, residential, other, street, and unknown labels are distinct."""
    crs = "EPSG:3157"
    parks = gpd.GeoDataFrame(geometry=[box(0, 0, 1, 1)], crs=crs)
    parcels = gpd.GeoDataFrame(geometry=[box(1, 0, 2, 1), box(3, 0, 4, 1)], crs=crs)
    zoning = gpd.GeoDataFrame(
        {
            "zoning_classification": ["Residential", "Commercial"],
            "zoning_category": ["R1", "C"],
        },
        geometry=[box(1, 0, 2, 1), box(3, 0, 4, 1)],
        crs=crs,
    )
    roads = gpd.GeoDataFrame(geometry=[LineString([(0, 10), (6, 10)])], crs=crs)
    paths = {}
    for name, frame in [
        ("parks", parks),
        ("parcels", parcels),
        ("zoning", zoning),
        ("roads", roads),
    ]:
        path = tmp_path / f"{name}.gpkg"
        frame.to_file(path, driver="GPKG")
        paths[name] = path
    labels = classify_land_context(
        np.asarray([0.5, 1.5, 3.5, 0.5, 5.5]),
        np.asarray([0.5, 0.5, 0.5, 10.0, 0.5]),
        parcels_path=paths["parcels"],
        parks_path=paths["parks"],
        roads_path=paths["roads"],
        zoning_path=paths["zoning"],
        road_buffer_m=0.2,
    )
    assert labels == [
        "public park",
        "likely private parcel",
        "other parcel",
        "street/lane",
        "unknown",
    ]


def _crown(tree_id: str, x: float, height: float) -> DetectedTree:
    """Build a detected crown for candidate tests."""
    return DetectedTree(tree_id, 0, 0, height, 3.0, 28.3, x, 0.5, -123.0, 49.0)


def test_build_city_candidates_excludes_building_centres(tmp_path: Path) -> None:
    """A crown centred on a building mask is not a candidate."""
    mask_path = tmp_path / "building.tif"
    values = np.zeros((4, 4), dtype=np.uint8)
    values[3, 2] = 1
    with rasterio.open(
        mask_path,
        "w",
        driver="GTiff",
        height=4,
        width=4,
        count=1,
        dtype="uint8",
        crs="EPSG:3157",
        transform=rasterio.transform.from_origin(0.0, 4.0, 1.0, 1.0),
    ) as dataset:
        dataset.write(values, 1)
    detected = (_crown("d1", 0.5, 12.0), _crown("d2", 2.5, 62.0))
    match = CityMatch(0, ("d1", "d2"), ())
    candidates = build_city_candidates(
        detected,
        match,
        (),
        ["likely private parcel", "likely private parcel"],
        building_mask_path=mask_path,
    )
    assert len(candidates) == 1
    assert candidates[0].height_m == 12.0
    assert candidates[0].confidence >= 0.6


def test_write_city_candidates_writes_summary_and_geojson(tmp_path: Path) -> None:
    """The summary has counts and the compressed GeoJSON has derived attributes."""
    candidate = OffInventoryCandidate(
        "off-000001",
        "city-1",
        -123.0,
        49.0,
        0.0,
        0.0,
        12.0,
        3.0,
        28.3,
        10.0,
        "likely private parcel",
        0.7,
        ("test",),
    )
    summary_path = write_city_candidates(
        (candidate,),
        dataset_id="test",
        detected_count=2,
        matched_count=1,
        unmatched_inventory_count=0,
        out_dir=tmp_path,
    )
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["candidate_count"] == 1
    assert summary["high_confidence_count"] == 1
    assert summary["land_classes"] == {"likely private parcel": 1}
    with gzip.open(tmp_path / "off_inventory.geojson.gz", "rt", encoding="utf-8") as handle:
        collection = json.load(handle)
    assert collection["features"][0]["properties"]["dbh_cm"] > 0
    assert collection["features"][0]["geometry"] == {
        "type": "Point",
        "coordinates": [-123.0, 49.0],
    }
