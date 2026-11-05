"""Tests for the full Vancouver inventory evidence layer."""

from __future__ import annotations

from pathlib import Path

import pytest

from fresh_urban_forest.city_inventory import (
    height_comparison,
    inventory_summary,
    load_city_inventory,
)
from fresh_urban_forest.models import TreeRecord


def test_load_city_inventory_counts_unmapped_and_outliers(tmp_path: Path) -> None:
    """Unmapped rows and implausible diameters are counted, not silently dropped."""
    path = tmp_path / "trees.csv"
    path.write_text(
        "asset_id,address,common_name,genus_name,species_name,cultivar_name,height_m,"
        "diameter_cm,local_area,geom,geo_point_2d\n"
        "1,1 Main St,Red maple,ACER,RUBRUM,NONE,12.5,30.0,Kitsilano,"
        '"{""coordinates"": [-123.25, 49.26], ""type"": ""Point""}",'
        '"49.26, -123.25"\n'
        "2,2 Main St,Red maple,ACER,RUBRUM,NONE,12.5,400.0,Kitsilano,"
        '"{""coordinates"": [-123.2501, 49.2601], ""type"": ""Point""}",'
        '"49.2601, -123.2501"\n'
        "3,3 Main St,Red maple,ACER,RUBRUM,NONE,12.5,30.0,Kitsilano,,,\n",
        encoding="utf-8",
    )
    inventory = load_city_inventory(path)
    assert inventory.source_rows == 3
    assert len(inventory.trees) == 2
    assert inventory.unmapped_rows == 1
    assert inventory.dbh_outliers == 1
    summary = inventory_summary(inventory)
    assert summary["mapped_rows"] == 2
    assert summary["unmapped_rows"] == 1
    assert summary["dbh_outliers"] == 1


def test_height_comparison_reports_bias_and_rmse() -> None:
    """Inventory and LiDAR height differences are reported explicitly."""
    trees = (
        TreeRecord(tree_id="a", lon=0.0, lat=0.0, height_m=10.0, lidar_height_m=12.0),
        TreeRecord(tree_id="b", lon=0.0, lat=0.0, height_m=20.0, lidar_height_m=18.0),
        TreeRecord(tree_id="c", lon=0.0, lat=0.0, height_m=None, lidar_height_m=12.0),
    )
    result = height_comparison(trees)
    overall = result["overall"]
    assert isinstance(overall, dict)
    assert overall["n"] == 2
    assert overall["bias_m"] == pytest.approx(0.0)
    assert overall["rmse_m"] == pytest.approx(2.0)
    assert overall["mae_m"] == pytest.approx(2.0)
