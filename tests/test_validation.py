"""Tests for detection-versus-inventory validation."""

from __future__ import annotations

import json
from pathlib import Path

from fresh_urban_forest.itd import DetectedTree
from fresh_urban_forest.models import TreeRecord
from fresh_urban_forest.validation import validate_detection, write_validation


def _crown(tree_id: str, x: float, y: float, height: float, radius: float) -> DetectedTree:
    """Build a detected crown."""
    return DetectedTree(
        tree_id=tree_id,
        row=0,
        col=0,
        height_m=height,
        crown_radius_m=radius,
        crown_area_m2=3.14159 * radius**2,
        x=x,
        y=y,
        lon=-123.25 + x / 100000.0,
        lat=49.26 + y / 100000.0,
    )


def _tree(tree_id: str, x: float, y: float, height: float, crown: float) -> TreeRecord:
    """Build an inventory tree."""
    return TreeRecord(
        tree_id=tree_id,
        lon=-123.25 + x / 100000.0,
        lat=49.26 + y / 100000.0,
        species="Acer rubrum",
        height_m=height,
        crown_width_m=crown,
        x_m=x,
        y_m=y,
    )


def test_validate_detection_matches_nearest_trees() -> None:
    """Nearest trees within tolerance match and the rest are reported unmatched."""
    detected = [_crown("d1", 0.0, 0.0, 12.0, 3.0), _crown("d2", 10.0, 0.0, 10.0, 2.0)]
    trees = [_tree("t1", 0.5, 0.0, 11.0, 6.0), _tree("t2", 30.0, 0.0, 9.0, 4.0)]
    result = validate_detection(detected, trees, max_distance_m=5.0)
    assert result.detected_count == 2
    assert result.inventory_count == 2
    assert result.matched_count == 1
    assert result.precision == 0.5
    assert result.recall == 0.5
    assert result.f1 == 0.5
    assert result.mean_distance_m == 0.5
    assert result.mean_height_delta_m == 1.0
    assert result.height_rmse_m == 1.0
    assert result.unmatched_detected == ("d2",)
    assert result.unmatched_inventory == ("t2",)
    assert result.matches[0].tree_id == "t1"


def test_validate_detection_writes_json_and_geojson(tmp_path: Path) -> None:
    """Validation output is portable and keeps matched coordinates."""
    detected = [_crown("d1", 0.0, 0.0, 12.0, 3.0)]
    trees = [_tree("t1", 0.5, 0.0, 11.0, 6.0)]
    result = validate_detection(detected, trees)
    path = write_validation(result, tmp_path)
    payload = json.loads(path.read_text())
    assert payload["matched_count"] == 1
    assert payload["method"].startswith("Greedy nearest")
    geojson = json.loads((tmp_path / "detection_validation.geojson").read_text())
    assert geojson["features"][0]["properties"]["status"] == "matched"
    assert geojson["features"][0]["geometry"]["coordinates"] != [0.0, 0.0]


def test_validate_detection_handles_empty_inputs() -> None:
    """Empty inputs produce zero metrics rather than a division error."""
    result = validate_detection([], [])
    assert result.matched_count == 0
    assert result.precision == 0.0
    assert result.recall == 0.0
    assert result.f1 == 0.0
