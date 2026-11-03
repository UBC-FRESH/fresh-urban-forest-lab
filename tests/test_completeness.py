"""Tests for the inventory-completeness summary."""

from __future__ import annotations

from fresh_urban_forest.completeness import inventory_completeness
from fresh_urban_forest.models import TreeRecord


def test_completeness_uses_source_flags() -> None:
    """Measured flags override the presence of an imputed value."""
    measured = TreeRecord(
        tree_id="a",
        lon=0.0,
        lat=0.0,
        species="Acer rubrum",
        dbh_cm=20.0,
        height_m=10.0,
        crown_width_m=4.0,
        attributes={
            "dbh_measured": "true",
            "height_measured": "false",
            "crown_width_measured": "true",
            "species_measured": "true",
        },
    )
    imputed = TreeRecord(
        tree_id="b",
        lon=0.0,
        lat=0.0,
        species="",
        dbh_cm=10.0,
        height_m=8.0,
        crown_width_m=3.0,
        attributes={
            "dbh_measured": "false",
            "height_measured": "false",
            "crown_width_measured": "false",
            "species_measured": "false",
        },
    )
    removed = TreeRecord(tree_id="c", lon=0.0, lat=0.0, status="removed")
    summary = inventory_completeness([measured, imputed, removed])
    assert summary["total"] == 2
    fields = summary["fields"]
    assert isinstance(fields, dict)
    assert fields["dbh"]["measured"] == 1
    assert fields["dbh"]["fraction"] == 0.5
    assert fields["height"]["measured"] == 0
    assert fields["crown_width"]["measured"] == 1
    assert fields["species"]["measured"] == 1


def test_completeness_falls_back_to_values() -> None:
    """Without flags, a present value counts as measured."""
    tree = TreeRecord(
        tree_id="a",
        lon=0.0,
        lat=0.0,
        species="Acer rubrum",
        dbh_cm=20.0,
        height_m=None,
        crown_width_m=4.0,
    )
    summary = inventory_completeness([tree])
    fields = summary["fields"]
    assert isinstance(fields, dict)
    assert fields["dbh"]["fraction"] == 1.0
    assert fields["height"]["fraction"] == 0.0
    assert inventory_completeness([])["total"] == 0
