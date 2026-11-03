"""Tests for species grouping, allometry, and one-year growth."""

from __future__ import annotations

import math

import pytest

from fresh_urban_forest.allometry import (
    aboveground_biomass_kg,
    annual_dbh_increment_cm,
    carbon_kg,
    crown_volume_m3,
    estimate_crown_width_m,
    estimate_dbh_cm,
    estimate_height_m,
    grow_tree,
    is_native_species,
    profile_for,
    species_group,
    tree_carbon_kg,
    tree_crown_volume_m3,
)
from fresh_urban_forest.models import TreeRecord


def test_species_group_classifies_conifer_and_deciduous() -> None:
    """Conifer and deciduous keywords map to the right growth group."""
    assert species_group("Thuja plicata") == "conifer"
    assert species_group("Acer rubrum") == "deciduous"
    assert species_group("") == "unknown"
    assert species_group("Unidentified tree") == "unknown"


def test_native_species_recognises_local_names() -> None:
    """Native names match while exotic street trees do not."""
    assert is_native_species("Pseudotsuga menziesii") is True
    assert is_native_species("Acer platanoides") is False
    assert is_native_species("") is False


def test_allometric_estimates_are_monotonic_and_bounded() -> None:
    """Height, diameter, and crown width increase with size and respect caps."""
    small_height = estimate_height_m(10.0, "conifer")
    large_height = estimate_height_m(80.0, "conifer")
    assert small_height < large_height <= profile_for("Thuja plicata").max_height_m
    assert estimate_dbh_cm(small_height, "conifer") < estimate_dbh_cm(large_height, "conifer")
    assert estimate_crown_width_m(10.0, "deciduous") < estimate_crown_width_m(80.0, "deciduous")


def test_crown_volume_is_positive_and_scales_with_width() -> None:
    """Crown volume follows the ellipsoid formula."""
    volume = crown_volume_m3(20.0, 8.0, 0.5)
    assert volume == pytest.approx(math.pi / 6.0 * 64.0 * 10.0)
    assert crown_volume_m3(20.0, 16.0, 0.5) > volume


def test_biomass_and_carbon_follow_the_jenkins_form() -> None:
    """Carbon is half of above-ground biomass and both increase with diameter."""
    softwood = aboveground_biomass_kg(30.0, "conifer")
    hardwood = aboveground_biomass_kg(30.0, "deciduous")
    assert softwood > 0
    assert hardwood > 0
    assert carbon_kg(30.0, "conifer") == pytest.approx(softwood / 2.0)
    assert aboveground_biomass_kg(40.0, "conifer") > softwood


def test_annual_increment_declines_with_size_and_clamps() -> None:
    """Small trees grow faster than large trees and increments stay plausible."""
    small = annual_dbh_increment_cm(5.0, "conifer")
    large = annual_dbh_increment_cm(150.0, "conifer")
    assert 0.01 <= large < small <= 1.5
    assert annual_dbh_increment_cm(5.0, "conifer", competition=0.1) < small


def test_grow_tree_fills_missing_dimensions_and_advances() -> None:
    """A tree with missing dimensions is completed before growth."""
    tree = TreeRecord(
        tree_id="t1",
        lon=-123.25,
        lat=49.26,
        species="Acer rubrum",
        common_name="Red maple",
        dbh_cm=None,
        height_m=None,
        crown_width_m=None,
        crown_ratio=0.5,
        source="test",
    )
    grown = grow_tree(tree, 5)
    assert grown.dbh_cm is not None
    assert grown.dbh_cm > 0
    assert grown.height_m is not None
    assert grown.height_m > 0
    assert grown.crown_width_m is not None
    assert grown.crown_width_m > 0
    assert grow_tree(tree, 0) == tree


def test_tree_level_carbon_and_volume_handle_missing_values() -> None:
    """Tree helpers return zero when the required dimensions are absent."""
    tree = TreeRecord(tree_id="t", lon=0.0, lat=0.0, species="Acer", dbh_cm=20.0, height_m=10.0)
    assert tree_carbon_kg(tree) > 0
    assert tree_crown_volume_m3(tree) >= 0
    assert tree_carbon_kg(TreeRecord(tree_id="x", lon=0.0, lat=0.0)) == 0.0
    assert tree_crown_volume_m3(TreeRecord(tree_id="x", lon=0.0, lat=0.0)) == 0.0
