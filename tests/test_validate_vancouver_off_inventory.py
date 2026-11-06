"""Tests for the held-out city validation command."""

from __future__ import annotations

import gzip
import json
from dataclasses import asdict
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from shapely.geometry import box

from fresh_urban_forest.city_validation import is_held_out_block
from fresh_urban_forest.itd import DetectedTree
from fresh_urban_forest.terrain import unproject_xy
from validate_vancouver_off_inventory import (
    attach_orthophoto_tiles,
    load_candidates,
    load_detected,
    load_trees,
    main,
    parse_args,
    write_audit_files,
)


def _held_out_xy() -> tuple[float, float]:
    for column in range(20):
        for row in range(20):
            if is_held_out_block((column, row)):
                return (column * 500.0 + 250.0, row * 500.0 + 250.0)
    raise AssertionError("no held-out block")


def test_parse_args_and_loaders(tmp_path: Path) -> None:
    """Arguments and compressed input helpers round-trip small records."""
    args = parse_args([])
    assert args.root.name == "vancouver_2022"

    trees_path = tmp_path / "trees.json.gz"
    with gzip.open(trees_path, "wt", encoding="utf-8") as handle:
        json.dump(
            [{"tree_id": "t1", "lon": -123.0, "lat": 49.0, "x_m": 1.0, "y_m": 2.0}],
            handle,
        )
    assert load_trees(trees_path)[0].tree_id == "t1"

    detection_path = tmp_path / "detected.json.gz"
    crown = DetectedTree("d1", 0, 0, 10.0, 3.0, 28.3, 1.0, 2.0, -123.0, 49.0)
    with gzip.open(detection_path, "wt", encoding="utf-8") as handle:
        json.dump([asdict(crown)], handle)
    assert load_detected(detection_path) == (crown,)

    candidates_path = tmp_path / "candidates.geojson.gz"
    with gzip.open(candidates_path, "wt", encoding="utf-8") as handle:
        json.dump({"type": "FeatureCollection", "features": []}, handle)
    assert load_candidates(candidates_path) == ()


def test_attach_orthophoto_and_write_audit(tmp_path: Path) -> None:
    """An audit row gains a tile and produces CSV, GeoJSON, and JSON."""
    index = gpd.GeoDataFrame(
        {
            "name": ["T1"],
            "mrsid_url": ["https://example.test/T1.zip"],
            "ecw_url": ["https://example.test/T1.ecw.zip"],
        },
        geometry=[box(-124, 48, -122, 50)],
        crs="EPSG:4326",
    )
    index_path = tmp_path / "index.gpkg"
    index.to_file(index_path, driver="GPKG")
    sample = (
        {
            "candidate_id": "c1",
            "lon": -123.0,
            "lat": 49.0,
            "x_m": 0.0,
            "y_m": 0.0,
            "confidence": 0.8,
            "confidence_band": "high",
            "land_class": "likely private parcel",
            "local_area": "A",
            "height_m": 10.0,
            "crown_radius_m": 3.0,
        },
    )
    enriched = attach_orthophoto_tiles(sample, index_path)
    assert enriched[0]["orthophoto_tile"] == "T1"
    write_audit_files(enriched, tmp_path)
    assert (tmp_path / "off_inventory_audit_sample.csv").exists()
    payload = json.loads((tmp_path / "off_inventory_audit_sample.json").read_text())
    assert payload["sample_size"] == 1


def test_main_writes_a_validation_report(tmp_path: Path) -> None:
    """The command writes a report from synthetic held-out data."""
    x, y = _held_out_xy()
    lon, lat = unproject_xy(x, y, "EPSG:3157")
    root = tmp_path / "out"
    root.mkdir()
    trees_path = tmp_path / "trees.json.gz"
    with gzip.open(trees_path, "wt", encoding="utf-8") as handle:
        json.dump(
            [{"tree_id": "t1", "lon": -123.0, "lat": 49.0, "x_m": x, "y_m": y}],
            handle,
        )
    detection_path = tmp_path / "detected.json.gz"
    crown = DetectedTree("d1", 0, 0, 10.0, 3.0, 28.3, x, y, -123.0, 49.0)
    with gzip.open(detection_path, "wt", encoding="utf-8") as handle:
        json.dump([asdict(crown)], handle)
    candidates_path = tmp_path / "candidates.geojson.gz"
    feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "candidate_id": "c1",
            "confidence": 0.8,
            "height_m": 10.0,
            "crown_radius_m": 3.0,
            "land_class": "likely private parcel",
        },
    }
    with gzip.open(candidates_path, "wt", encoding="utf-8") as handle:
        json.dump({"type": "FeatureCollection", "features": [feature]}, handle)
    areas = gpd.GeoDataFrame({"name": ["A"]}, geometry=[box(0, 0, 10000, 10000)], crs="EPSG:3157")
    areas_path = tmp_path / "areas.gpkg"
    areas.to_file(areas_path, driver="GPKG")
    index = gpd.GeoDataFrame(
        {"name": ["T1"], "mrsid_url": ["u"], "ecw_url": ["e"]},
        geometry=[box(-124, 48, -122, 50)],
        crs="EPSG:4326",
    )
    index_path = tmp_path / "index.gpkg"
    index.to_file(index_path, driver="GPKG")
    chm_path = tmp_path / "chm.tif"
    with rasterio.open(
        chm_path,
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=1,
        dtype="float32",
        crs="EPSG:3157",
        transform=rasterio.transform.from_origin(0.0, 10_000.0, 1000.0, 1000.0),
    ) as dataset:
        dataset.write(np.zeros((10, 10), dtype=np.float32), 1)
    # The test CHM bounds are 10 km; use the same frame as the synthetic features.
    from rasterio.transform import from_origin

    with rasterio.open(
        chm_path,
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=1,
        dtype="float32",
        crs="EPSG:3157",
        transform=from_origin(0.0, 10_000.0, 1000.0, 1000.0),
    ) as dataset:
        dataset.write(np.zeros((10, 10), dtype=np.float32), 1)
    result = main(
        [
            "--root",
            str(root),
            "--trees",
            str(trees_path),
            "--detected",
            str(detection_path),
            "--candidates",
            str(candidates_path),
            "--local-areas",
            str(areas_path),
            "--orthophoto-index",
            str(index_path),
            "--chm",
            str(chm_path),
        ]
    )
    assert result == 0
    report = json.loads((root / "off_inventory_validation.json").read_text())
    assert report["public_tree_recall"]["sample_size"] == 1
    assert report["candidate_audit"]["sample_size"] == 1
