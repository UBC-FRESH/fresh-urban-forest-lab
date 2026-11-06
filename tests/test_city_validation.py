"""Tests for held-out public-tree validation and candidate audit sampling."""

from __future__ import annotations

import geopandas as gpd
from shapely.geometry import box

from fresh_urban_forest.city_validation import (
    HeldOutTree,
    block_key,
    evaluate_public_recall,
    is_held_out_block,
    is_held_out_point,
    sample_candidate_audit,
    sample_public_trees,
    wilson_interval,
)
from fresh_urban_forest.itd import DetectedTree
from fresh_urban_forest.models import TreeRecord
from fresh_urban_forest.terrain import unproject_xy


def _held_out_center() -> tuple[float, float]:
    """Find a block centre that the fixed hash selects."""
    for column in range(20):
        for row in range(20):
            if is_held_out_block((column, row)):
                return (column * 500.0 + 250.0, row * 500.0 + 250.0)
    raise AssertionError("no held-out block")


def _area(name: str = "Test Area") -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"name": [name]},
        geometry=[box(0, 0, 10_000, 10_000)],
        crs="EPSG:3157",
    )


def test_wilson_interval_is_bounded() -> None:
    """The Wilson interval contains the observed proportion."""
    low, high = wilson_interval(50, 100)
    assert 0.39 < low < 0.41
    assert 0.59 < high < 0.61
    assert wilson_interval(0, 0) == (0.0, 0.0)


def test_block_selection_is_deterministic_and_uses_a_buffer() -> None:
    """A held-out block centre is selected, but its edge is not."""
    x, y = _held_out_center()
    bounds = (0.0, 0.0, 10_000.0, 10_000.0)
    assert block_key(x, y, bounds) == (int(x // 500), int(y // 500))
    assert is_held_out_point(x, y, bounds)
    assert not is_held_out_point(x - 250.0, y, bounds)


def test_sample_public_trees_is_stratified_and_deterministic() -> None:
    """Live trees in held-out blocks are sampled reproducibly by area."""
    x, y = _held_out_center()
    trees = tuple(
        TreeRecord(f"tree-{index}", -123.0, 49.0, x_m=x + index, y_m=y) for index in range(5)
    )
    sample_a = sample_public_trees(trees, _area(), (0.0, 0.0, 10_000.0, 10_000.0), sample_size=3)
    sample_b = sample_public_trees(trees, _area(), (0.0, 0.0, 10_000.0, 10_000.0), sample_size=3)
    assert len(sample_a) == 3
    assert [item.tree.tree_id for item in sample_a] == [item.tree.tree_id for item in sample_b]
    assert all(item.local_area == "Test Area" for item in sample_a)


def test_evaluate_public_recall_counts_nearest_crowns() -> None:
    """A crown within five metres counts as a recall hit."""
    x, y = _held_out_center()
    sample = tuple(
        HeldOutTree(TreeRecord(f"t{index}", -123.0, 49.0, x_m=x, y_m=y), "A") for index in range(3)
    )
    detected = (
        DetectedTree("d1", 0, 0, 10.0, 3.0, 28.3, x, y, -123.0, 49.0),
        DetectedTree("d2", 0, 0, 10.0, 3.0, 28.3, x + 6.0, y, -123.0, 49.0),
    )
    result = evaluate_public_recall(sample, detected)
    assert result["hit_count"] == 3
    assert result["recall"] == 1.0
    by_area = result["by_area"]
    assert isinstance(by_area, dict)
    assert by_area["A"]["sample"] == 3


def test_candidate_audit_uses_confidence_and_land_cells() -> None:
    """The audit sample is drawn across confidence and land strata."""
    x, y = _held_out_center()
    lon, lat = unproject_xy(x, y, "EPSG:3157")
    bands = ("low", "medium", "high")
    lands = ("likely private parcel", "street/lane", "public park", "other parcel", "unknown")
    features = []
    for index, (band, land) in enumerate((band, land) for band in bands for land in lands):
        confidence = {"low": 0.4, "medium": 0.6, "high": 0.8}[band]
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "candidate_id": f"c{index}",
                    "confidence": confidence,
                    "height_m": 10.0,
                    "crown_radius_m": 3.0,
                    "land_class": land,
                },
            }
        )
    sample = sample_candidate_audit(
        features,
        _area(),
        (0.0, 0.0, 10_000.0, 10_000.0),
        sample_size=15,
    )
    assert len(sample) == 15
    assert {row["confidence_band"] for row in sample} == {"low", "medium", "high"}
    assert {row["land_class"] for row in sample} == set(lands)
