"""Tests for Lower Mainland instance helpers."""

from __future__ import annotations

import numpy as np

from fresh_urban_forest.lower_mainland import (
    GridSpec,
    canopy_records_from_classes,
    class_canopy_height,
    class_species,
    grid_for_bounds,
    tree_inventory_summary,
)
from fresh_urban_forest.models import TreeRecord


def test_grid_for_bounds_rounds_outward() -> None:
    """The grid covers the requested projected bounds."""
    grid = grid_for_bounds((1.0, 2.0, 21.0, 12.0), resolution_m=5.0)
    assert grid.left == 0.0
    assert grid.top == 15.0
    assert grid.width == 5
    assert grid.height == 3
    assert grid.bounds == (0.0, 0.0, 25.0, 15.0)


def test_class_heights_and_labels_are_transparent() -> None:
    """Tree classes map to explicit screening assumptions."""
    assert class_canopy_height(6) == 16.0
    assert class_canopy_height(7) == 12.0
    assert class_canopy_height(8) == 4.0
    assert class_canopy_height(1) == 0.0
    assert class_species(6).startswith("Coniferous")
    assert class_species(7).startswith("Deciduous")
    assert class_species(1) == ""


def test_canopy_records_sample_tree_classes() -> None:
    """The canopy sampler uses tree classes and the requested spacing."""
    classes = np.zeros((10, 10), dtype=np.uint8)
    classes[1, 1] = 6
    classes[3, 5] = 7
    classes[5, 3] = 1
    grid = GridSpec(left=0.0, top=100.0, resolution_m=10.0, width=10, height=10)
    records = canopy_records_from_classes(classes, grid, step_m=20.0)
    assert len(records) == 2
    assert {record.species for record in records} == {
        "Coniferous (LCC 2020)",
        "Deciduous (LCC 2020)",
    }
    assert all(record.attributes["canopy_candidate"] == "true" for record in records)


def test_tree_inventory_summary_reports_unmeasured_fields() -> None:
    """A provisional inventory reports zero measured height and DBH."""
    tree = TreeRecord(
        "test:1",
        -123.0,
        49.0,
        species="Acer rubrum",
        height_m=12.0,
        dbh_cm=20.0,
        native=True,
        attributes={"height_measured": "false", "dbh_measured": "false"},
    )
    summary = tree_inventory_summary((tree,), source_rows=2)
    assert summary["source_rows"] == 2
    assert summary["mapped_rows"] == 1
    assert summary["unmapped_rows"] == 1
    assert summary["measured_height"] == 0
    assert summary["height_median_m"] == 12.0
