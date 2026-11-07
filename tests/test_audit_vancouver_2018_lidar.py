"""Tests for the 2018 City LiDAR manifest and coverage audit."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import geopandas as gpd
import pytest
from shapely.geometry import box

from audit_vancouver_2018_lidar import (
    build_manifest,
    coverage_audit,
    main,
    parse_record,
)


def _record(name: str = "4800E_54550N") -> dict[str, object]:
    """Return one synthetic Open Data record."""
    return {
        "name": name,
        "lidar_url": f"https://example.test/{name}.zip",
        "geom": {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-123.28, 49.24],
                        [-123.28, 49.26],
                        [-123.26, 49.26],
                        [-123.26, 49.24],
                        [-123.28, 49.24],
                    ]
                ],
            },
        },
    }


def test_parse_record_and_manifest() -> None:
    """Records are normalized and sorted."""
    tile = parse_record(_record("b"))
    assert tile["tile_id"] == "b"
    assert tile["bbox"] == [-123.28, 49.24, -123.26, 49.26]
    manifest = build_manifest([_record("b"), _record("a")], generated_utc="2026-11-07T00:00:00Z")
    assert manifest["tile_count"] == 2
    tiles = cast("list[Mapping[str, object]]", manifest["tiles"])
    assert [item["tile_id"] for item in tiles] == ["a", "b"]


def test_parse_record_rejects_incomplete() -> None:
    """Missing id, URL, or geometry is rejected."""
    with pytest.raises(ValueError, match="missing"):
        parse_record({"name": "x"})
    with pytest.raises(ValueError, match="geometry"):
        parse_record({"name": "x", "lidar_url": "https://example.test/x.zip", "geom": {}})


def _boundary(tmp_path: Path) -> Path:
    """Write a small WGS84 boundary fixture."""
    path = tmp_path / "boundary.geojson"
    frame = gpd.GeoDataFrame(
        {"name": ["test"]},
        geometry=[box(-123.28, 49.24, -123.26, 49.26)],
        crs="EPSG:4326",
    )
    frame.to_file(path, driver="GeoJSON")
    return path


def test_coverage_audit_counts_existing_tiles(tmp_path: Path) -> None:
    """Coverage, present files, and missing tiles are reported."""
    boundary = _boundary(tmp_path)
    existing = tmp_path / "existing"
    existing.mkdir()
    (existing / "a.zip").write_bytes(b"placeholder")
    manifest = build_manifest([_record("a"), _record("b")], generated_utc="2026-11-07T00:00:00Z")
    audit = coverage_audit(manifest, boundary_path=boundary, existing_dir=existing)
    assert audit["tile_count"] == 2
    assert audit["downloaded_tile_count"] == 1
    assert audit["missing_tile_count"] == 1
    assert audit["missing_tiles"] == ["b"]
    assert float(cast(float, audit["coverage_fraction"])) > 0.0
    assert "webtransfer" in str(audit["download_blocker"])


def test_coverage_audit_requires_boundary(tmp_path: Path) -> None:
    """A missing boundary is an explicit error."""
    manifest = build_manifest([_record()], generated_utc="2026-11-07T00:00:00Z")
    with pytest.raises(FileNotFoundError):
        coverage_audit(manifest, boundary_path=tmp_path / "missing.geojson", existing_dir=tmp_path)


def test_main_writes_manifest(tmp_path: Path) -> None:
    """The operator path writes a manifest and prints an audit."""
    boundary = _boundary(tmp_path)
    records_path = tmp_path / "records.json"
    records_path.write_text(json.dumps([_record("a")]), encoding="utf-8")
    out = tmp_path / "tiles.json"
    assert (
        main(
            [
                "--records",
                str(records_path),
                "--out",
                str(out),
                "--boundary",
                str(boundary),
                "--existing",
                str(tmp_path / "none"),
            ]
        )
        == 0
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["tile_count"] == 1
