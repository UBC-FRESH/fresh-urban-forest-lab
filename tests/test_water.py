"""Tests for the single-bucket tree water balance."""

from __future__ import annotations

import pytest

from fresh_urban_forest.species import profile_for_species
from fresh_urban_forest.water import (
    ClimateSeries,
    compare_water_policies,
    simulate_water_balance,
    water_summary,
)


def test_irrigation_reduces_stress_and_costs_money() -> None:
    """A moisture-triggered policy uses more water and has no more stress than none."""
    profile = profile_for_species("Acer rubrum")
    dry = simulate_water_balance(
        profile,
        crown_area_m2=20.0,
        soil_volume_m3=2.0,
        sun_fraction=0.9,
        policy="none",
    )
    watered = simulate_water_balance(
        profile,
        crown_area_m2=20.0,
        soil_volume_m3=2.0,
        sun_fraction=0.9,
        policy="moisture_trigger",
    )
    assert watered.irrigation_l > dry.irrigation_l
    assert watered.stress_days <= dry.stress_days
    assert watered.annual_cost_cad > dry.annual_cost_cad


def test_policy_comparison_returns_every_policy() -> None:
    """The policy table covers none, establishment, fixed, trigger, and deficit."""
    options = compare_water_policies(
        profile_for_species("Thuja plicata"),
        crown_area_m2=12.0,
        soil_volume_m3=8.0,
        sun_fraction=0.4,
        age_years=2.0,
    )
    assert {option.policy for option in options} == {
        "none",
        "establishment",
        "fixed",
        "moisture_trigger",
        "deficit",
    }
    assert all(option.evidence.tier == "prior" for option in options)


def test_large_soil_volume_reduces_stress() -> None:
    """A larger root volume buffers drought."""
    profile = profile_for_species("Acer rubrum")
    small = simulate_water_balance(
        profile,
        crown_area_m2=25.0,
        soil_volume_m3=1.0,
        sun_fraction=0.9,
        policy="none",
    )
    large = simulate_water_balance(
        profile,
        crown_area_m2=25.0,
        soil_volume_m3=20.0,
        sun_fraction=0.9,
        policy="none",
    )
    assert large.stress_days < small.stress_days


def test_climate_series_requires_twelve_months() -> None:
    """A malformed climate series is rejected."""
    with pytest.raises(ValueError, match="twelve"):
        ClimateSeries("bad", (1.0, 2.0), (1.0,) * 12, "test")


def test_water_summary_is_json_safe() -> None:
    """The summary exposes the main volumes, stress, and cost."""
    balance = simulate_water_balance(
        profile_for_species("Acer rubrum"),
        crown_area_m2=20.0,
        soil_volume_m3=6.0,
        sun_fraction=0.6,
    )
    payload = water_summary(balance)
    assert payload["policy"] == "none"
    assert float(str(payload["annual_cost_cad"])) >= 0.0
    assert "evidence" in payload
