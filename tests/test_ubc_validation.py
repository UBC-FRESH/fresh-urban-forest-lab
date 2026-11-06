"""Tests for independent UBC matching and attribute residuals."""

from __future__ import annotations

import geopandas as gpd
from shapely.geometry import Point

from fresh_urban_forest.itd import DetectedTree
from fresh_urban_forest.models import TreeRecord
from fresh_urban_forest.ubc_validation import (
    attribute_errors,
    one_to_one_matches,
    ubc_tree_records,
)


def _inventory() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "TREEID": ["1", "2"],
            "LIVE_TREE": ["Live", "Dead"],
            "TREE_STATUS": [None, None],
            "TAXA": ["Acer", "Acer"],
            "COMMON_NAME": ["Maple", "Maple"],
            "DBH": [20.0, 10.0],
            "THEIGHT": [10.0, 5.0],
            "CROWNWIDTH1": [4.0, 2.0],
            "CROWNWIDTH2": [6.0, 2.0],
        },
        geometry=[Point(-123.0, 49.0), Point(-123.0, 49.0)],
        crs="EPSG:4326",
    )


def test_ubc_tree_records_filters_dead_and_averages_crown() -> None:
    """Dead records are dropped and paired crown widths are averaged."""
    trees = ubc_tree_records(_inventory())
    assert len(trees) == 1
    assert trees[0].crown_width_m == 5.0
    assert trees[0].height_m == 10.0


def test_one_to_one_matches_and_missed_distance() -> None:
    """A tree can consume only one detected crown; missed distances are reported."""
    trees = (
        TreeRecord("1", -123.0, 49.0, x_m=0.0, y_m=0.0, height_m=10.0),
        TreeRecord("2", -123.0, 49.0, x_m=20.0, y_m=0.0, height_m=10.0),
    )
    detected = (DetectedTree("d1", 0, 0, 10.0, 3.0, 28.3, 0.2, 0.0, -123.0, 49.0),)
    mapping, summary = one_to_one_matches(detected, trees)
    assert mapping == {0: 0}
    assert summary.matched == 1
    assert summary.recall == 0.5
    assert summary.missed_nearest_distance_p50_m is not None


def test_attribute_errors_are_reported_for_matched_records() -> None:
    """Height, crown, and DBH residuals are finite for matched records."""
    trees = (
        TreeRecord(
            "1",
            -123.0,
            49.0,
            x_m=0.0,
            y_m=0.0,
            height_m=10.0,
            crown_width_m=6.0,
            dbh_cm=20.0,
        ),
    )
    detected = (DetectedTree("d1", 0, 0, 11.0, 3.0, 28.3, 0.2, 0.0, -123.0, 49.0),)
    errors = attribute_errors({0: 0}, detected, trees)
    assert errors["height_m"]["n"] == 1  # type: ignore[index]
    assert errors["crown_width_m"]["n"] == 1  # type: ignore[index]
    assert errors["dbh_cm"]["n"] == 1  # type: ignore[index]
