"""Tests for irrigation-policy comparison."""

from __future__ import annotations

from fresh_urban_forest.irrigation import compare_irrigation
from fresh_urban_forest.species import profile_for_species


def test_irrigation_options_rank_and_price_shade() -> None:
    """Every policy appears once and cost per shade-hour is finite."""
    options = compare_irrigation(
        profile_for_species("Acer rubrum"),
        crown_area_m2=20.0,
        soil_volume_m3=6.0,
        sun_fraction=0.6,
        shade_area_hours=500.0,
    )
    assert len(options) == 5
    assert {option.balance.policy for option in options} == {
        "none",
        "establishment",
        "fixed",
        "moisture_trigger",
        "deficit",
    }
    assert options[0].recommendation in {"best balance", "low cost", "high stress", "high cost"}
    assert all(option.cost_per_shade_hour >= 0.0 for option in options)
    assert all("cost_per_shade_hour" in option.to_dict() for option in options)


def test_zero_shade_uses_a_floor() -> None:
    """A zero shade denominator does not divide by zero."""
    options = compare_irrigation(
        profile_for_species("Thuja plicata"),
        crown_area_m2=12.0,
        soil_volume_m3=8.0,
        sun_fraction=0.4,
        shade_area_hours=0.0,
    )
    assert all(option.cost_per_shade_hour >= 0.0 for option in options)
