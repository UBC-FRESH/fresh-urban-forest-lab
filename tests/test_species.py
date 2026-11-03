"""Tests for species traits and site fit."""

from __future__ import annotations

import pytest

from fresh_urban_forest.species import (
    all_profiles,
    profile_for_species,
    rank_species,
    site_fit,
)


def test_profiles_include_exact_species_and_group_fallbacks() -> None:
    """Exact names, genera, and unknown names resolve to a profile."""
    assert profile_for_species("Acer rubrum").common_name == "Red maple"
    assert profile_for_species("Acer").group == "deciduous"
    unknown = profile_for_species("Imaginary tree")
    assert unknown.group == "unknown"
    assert len(all_profiles()) >= 10
    assert all(profile.source for profile in all_profiles())


def test_site_fit_rewards_matching_light_and_soil() -> None:
    """A sun-demanding species scores better in sun than deep shade."""
    profile = profile_for_species("Gleditsia triacanthos")
    sunny = site_fit(profile, sun_fraction=0.9, soil_volume_m3=8.0)
    shaded = site_fit(profile, sun_fraction=0.1, soil_volume_m3=8.0)
    assert sunny.score > shaded.score
    assert "light" in shaded.limiting_factors


def test_site_fit_penalises_low_soil_volume() -> None:
    """A small soil volume becomes a limiting factor."""
    profile = profile_for_species("Thuja plicata")
    fit = site_fit(profile, sun_fraction=0.4, soil_volume_m3=1.0)
    assert fit.soil_score < 0.2
    assert "soil volume" in fit.limiting_factors


def test_rank_species_is_descending() -> None:
    """Ranking returns the highest score first."""
    fits = rank_species(
        ("Acer rubrum", "Gleditsia triacanthos", "Thuja plicata"),
        sun_fraction=0.9,
        soil_volume_m3=8.0,
    )
    assert len(fits) == 3
    assert fits[0].score >= fits[-1].score
    assert all("evidence" in fit.to_dict() for fit in fits)


def test_fit_scores_are_bounded() -> None:
    """Extreme inputs remain inside the documented zero-to-one range."""
    profile = profile_for_species("Acer macrophyllum")
    fit = site_fit(
        profile,
        sun_fraction=2.0,
        soil_volume_m3=-1.0,
        water_availability=-2.0,
        heat_exposure=4.0,
        space_available_m=-1.0,
    )
    assert 0.0 <= fit.score <= 1.0
    assert pytest.approx(fit.score) == fit.score
