"""Tests for local height-diameter calibration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fresh_urban_forest.calibration import (
    fit_allometry,
    fit_height_diameter,
    write_allometry,
)
from fresh_urban_forest.models import TreeRecord


def _tree(index: int, dbh: float, height: float, species: str = "Acer rubrum") -> TreeRecord:
    """Build a measured tree with a known height-diameter relationship."""
    return TreeRecord(
        tree_id=f"t{index}",
        lon=-123.25,
        lat=49.26,
        species=species,
        dbh_cm=dbh,
        height_m=height,
        attributes={
            "dbh_measured": "true",
            "height_measured": "true",
            "species_measured": "true",
        },
    )


def test_fit_height_diameter_recovers_a_known_curve() -> None:
    """A clean power law is recovered with a high R-squared."""
    trees = [_tree(index, dbh, 1.3 + 2.0 * dbh**0.6) for index, dbh in enumerate(range(5, 65, 2))]
    fit = fit_height_diameter(trees, "deciduous", min_samples=10)
    assert fit is not None
    assert fit.coefficient == pytest.approx(2.0, rel=0.02)
    assert fit.exponent == pytest.approx(0.6, rel=0.02)
    assert fit.r2 > 0.99
    assert fit.sample_size == len(trees)


def test_fit_height_diameter_needs_enough_samples() -> None:
    """Too few measured trees returns no fit."""
    trees = [_tree(1, 10.0, 8.0)]
    assert fit_height_diameter(trees, "deciduous", min_samples=20) is None


def test_fit_allometry_and_write(tmp_path: Path) -> None:
    """Group fits are written as a portable JSON product."""
    trees = [_tree(index, dbh, 1.3 + 2.0 * dbh**0.6) for index, dbh in enumerate(range(5, 65, 2))]
    trees += [
        _tree(index + 100, dbh, 1.3 + 1.5 * dbh**0.7, species="Thuja plicata")
        for index, dbh in enumerate(range(5, 65, 2))
    ]
    fits = fit_allometry(trees, min_samples=10)
    assert set(fits) == {"conifer", "deciduous"}
    path = write_allometry(fits, tmp_path / "allometry.json")
    payload = json.loads(path.read_text())
    assert payload["schema_version"]
    assert payload["fits"]["conifer"]["sample_size"] > 0
