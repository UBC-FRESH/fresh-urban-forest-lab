"""Tests for per-crown vegetation point support."""

from __future__ import annotations

import gzip
import json
import zipfile
from pathlib import Path

import laspy
import numpy as np

from build_vancouver_point_support import count_tile, load_candidates, main
from fresh_urban_forest.point_support import crown_support, support_rows, tile_id, tile_origin


def test_tile_helpers() -> None:
    """Tile identifiers round-trip through their lower-left origin."""
    assert tile_id(491_123.0, 5_457_999.0) == "491000_5457000"
    assert tile_origin("491000_5457000") == (491000.0, 5457000.0)


def test_crown_support_sums_a_disk() -> None:
    """Only count cells inside the candidate crown radius."""
    counts = np.zeros((10, 10), dtype=np.uint32)
    counts[4, 4] = 5
    counts[4, 5] = 7
    counts[5, 4] = 3
    count, density = crown_support(counts, 4.5, 4.5, 2.0, left=0.0, bottom=0.0)
    assert count == 15
    assert density > 0
    rows = support_rows(
        counts,
        [{"candidate_id": "c1", "x_m": 4.5, "y_m": 4.5, "crown_radius_m": 2.0}],
        left=0.0,
        bottom=0.0,
    )
    assert rows[0]["point_count"] == 15


def test_load_candidates_groups_by_tile(tmp_path: Path) -> None:
    """Candidate features are projected and grouped by their 1 km tile."""
    path = tmp_path / "candidates.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [-123.0, 49.0]},
                        "properties": {
                            "candidate_id": "c1",
                            "crown_radius_m": 3.0,
                            "height_m": 10.0,
                            "confidence": 0.8,
                            "land_class": "likely private parcel",
                        },
                    }
                ],
            },
            handle,
        )
    grouped = load_candidates(path)
    assert len(grouped) == 1


def test_count_tile_reads_a_synthetic_las(tmp_path: Path) -> None:
    """A synthetic vegetation point appears in the 1 m count grid."""
    las_path = tmp_path / "tile.las"
    header = laspy.LasHeader(point_format=0, version="1.2")
    header.offsets = [491000.0, 5457000.0, 0.0]
    header.scales = [0.01, 0.01, 0.01]
    las = laspy.LasData(header)
    las.x = np.asarray([491001.2])
    las.y = np.asarray([5457001.3])
    las.z = np.asarray([10.0])
    las.classification = np.asarray([5], dtype=np.uint8)
    las.write(las_path)
    zip_path = tmp_path / "491000_5457000.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.write(las_path, arcname=las_path.name)
    counts = count_tile(zip_path, "491000_5457000", tmp_path / "scratch")
    assert counts[1, 1] == 1


def test_point_support_main_writes_rows(tmp_path: Path) -> None:
    """The command processes one synthetic tile and writes support rows."""
    from fresh_urban_forest.terrain import unproject_xy

    lon, lat = unproject_xy(491001.2, 5457001.3, "EPSG:3157")
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
                            "crown_radius_m": 3.0,
                            "height_m": 10.0,
                            "confidence": 0.8,
                            "land_class": "likely private parcel",
                        },
                    }
                ],
            },
            handle,
        )
    las_path = tmp_path / "tile.las"
    header = laspy.LasHeader(point_format=0, version="1.2")
    header.offsets = [491000.0, 5457000.0, 0.0]
    header.scales = [0.01, 0.01, 0.01]
    las = laspy.LasData(header)
    las.x = np.asarray([491001.2])
    las.y = np.asarray([5457001.3])
    las.z = np.asarray([10.0])
    las.classification = np.asarray([5], dtype=np.uint8)
    las.write(las_path)
    raw = tmp_path / "raw"
    raw.mkdir()
    with zipfile.ZipFile(raw / "491000_5457000.zip", "w") as archive:
        archive.write(las_path, arcname=las_path.name)
    output = tmp_path / "support.json.gz"
    assert (
        main(
            [
                "--candidates",
                str(candidates),
                "--raw-dir",
                str(raw),
                "--output",
                str(output),
                "--limit",
                "1",
                "--jobs",
                "1",
            ]
        )
        == 0
    )
    with gzip.open(output, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert payload[0]["candidate_id"] == "c1"
    assert payload[0]["point_count"] >= 1
