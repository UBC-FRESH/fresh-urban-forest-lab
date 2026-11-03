"""Tests for light-water-growth-vigour modifiers."""

from __future__ import annotations

from fresh_urban_forest.species import profile_for_species
from fresh_urban_forest.vigor import growth_response, project_species_growth
from fresh_urban_forest.water import simulate_water_balance


def test_water_stress_reduces_the_growth_modifier() -> None:
    """A stressed tree has a lower water modifier and vigour."""
    profile = profile_for_species("Acer rubrum")
    dry = simulate_water_balance(
        profile,
        crown_area_m2=25.0,
        soil_volume_m3=0.5,
        sun_fraction=1.0,
        policy="none",
    )
    wet = simulate_water_balance(
        profile,
        crown_area_m2=25.0,
        soil_volume_m3=20.0,
        sun_fraction=1.0,
        policy="moisture_trigger",
    )
    dry_response = growth_response(
        profile,
        sun_fraction=1.0,
        water=dry,
        soil_volume_m3=0.5,
    )
    wet_response = growth_response(
        profile,
        sun_fraction=1.0,
        water=wet,
        soil_volume_m3=20.0,
    )
    assert dry_response.water_modifier < wet_response.water_modifier
    assert dry_response.vigor_score < wet_response.vigor_score
    assert dry_response.combined > 0.0


def test_shade_tolerant_species_prefers_shade() -> None:
    """A shade-tolerant cedar scores better in shade than a sun-demanding locust."""
    cedar = profile_for_species("Thuja plicata")
    locust = profile_for_species("Gleditsia triacanthos")
    water = simulate_water_balance(
        cedar,
        crown_area_m2=12.0,
        soil_volume_m3=8.0,
        sun_fraction=0.2,
    )
    cedar_response = growth_response(
        cedar,
        sun_fraction=0.2,
        water=water,
        soil_volume_m3=8.0,
    )
    locust_response = growth_response(
        locust,
        sun_fraction=0.2,
        water=water,
        soil_volume_m3=8.0,
    )
    assert cedar_response.light_modifier > locust_response.light_modifier


def test_projection_has_yearly_points_and_evidence() -> None:
    """A growth projection includes year zero through the horizon."""
    profile = profile_for_species("Quercus rubra")
    water = simulate_water_balance(
        profile,
        crown_area_m2=25.0,
        soil_volume_m3=10.0,
        sun_fraction=0.8,
    )
    response = growth_response(
        profile,
        sun_fraction=0.8,
        water=water,
        soil_volume_m3=10.0,
    )
    projection = project_species_growth(profile, response, initial_dbh_cm=10.0, years=5)
    assert len(projection.points) == 6
    assert projection.points[0].dbh_cm == 10.0
    assert projection.points[-1].dbh_cm >= projection.points[0].dbh_cm
    assert "evidence" in projection.to_dict()
