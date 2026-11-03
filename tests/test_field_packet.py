"""Tests for field-validation packets."""

from __future__ import annotations

import csv
from pathlib import Path

from fresh_urban_forest.field_packet import build_field_packet
from fresh_urban_forest.itd import DetectedTree
from fresh_urban_forest.models import TreeRecord


def _tree(tree_id: str, lon: float = -123.25, lat: float = 49.26) -> TreeRecord:
    """Build an inventory tree."""
    return TreeRecord(
        tree_id=tree_id,
        lon=lon,
        lat=lat,
        species="Acer rubrum",
        dbh_cm=20.0,
        height_m=12.0,
        crown_width_m=6.0,
        attributes={
            "dbh_measured": "true",
            "height_measured": "false",
            "crown_width_measured": "true",
        },
    )


def _crown(tree_id: str, lon: float = -123.25, lat: float = 49.26) -> DetectedTree:
    """Build a detected crown."""
    return DetectedTree(
        tree_id=tree_id,
        row=0,
        col=0,
        height_m=12.5,
        crown_radius_m=3.1,
        crown_area_m2=30.0,
        x=0.0,
        y=0.0,
        lon=lon,
        lat=lat,
    )


def test_build_field_packet_writes_files(tmp_path: Path) -> None:
    """The packet has tree, crown, checklist, and protocol files."""
    path = build_field_packet(
        [_tree("t1"), _tree("t2"), _tree("outside", lon=-123.0, lat=49.0)],
        [_crown("d1"), _crown("outside", lon=-123.0, lat=49.0)],
        bbox_wgs84=(-123.26, 49.25, -123.24, 49.27),
        out_dir=tmp_path,
    )
    assert path.name == "README.md"
    assert (tmp_path / "field_trees.geojson").exists()
    assert (tmp_path / "detected_crowns.geojson").exists()
    assert "complete-reference patch" in path.read_text()
    with (tmp_path / "field_checks.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert rows[0]["tree_id"] == "t1"
    assert rows[0]["dbh_measured"] == "true"
    assert rows[0]["field_verified"] == ""


def test_build_field_packet_respects_max_trees(tmp_path: Path) -> None:
    """The checklist is capped and sorted by tree id."""
    trees = [_tree(f"t{index}") for index in range(10)]
    build_field_packet(
        trees,
        [],
        bbox_wgs84=(-123.26, 49.25, -123.24, 49.27),
        out_dir=tmp_path,
        max_trees=3,
    )
    with (tmp_path / "field_checks.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["tree_id"] for row in rows] == ["t0", "t1", "t2"]
