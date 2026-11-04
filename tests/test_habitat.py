"""Tests for 3D canopy habitat metrics and guild suitability."""

from __future__ import annotations

from pathlib import Path

from fresh_urban_forest.habitat import (
    GUILDS,
    bird_report,
    guild_habitat,
    habitat_metrics,
    load_observations_csv,
)
from tests.fixtures import make_dataset


def test_habitat_metrics_are_bounded_and_structural(tmp_path: Path) -> None:
    """Habitat metrics expose structural values in their documented ranges."""
    dataset = make_dataset(tmp_path)
    metrics = habitat_metrics(dataset.trees, dataset.terrain)
    assert metrics.tree_count > 0
    assert 0.0 <= metrics.native_fraction <= 1.0
    assert metrics.p95_height_m >= metrics.mean_height_m >= 0.0
    assert 0.0 <= metrics.canopy_cover_pct <= 100.0
    assert 0.0 <= metrics.gap_fraction <= 1.0
    assert 0.0 <= metrics.vertical_complexity <= 1.0
    assert 0.0 <= metrics.foliage_height_diversity <= 1.0
    assert 0 <= metrics.layering_count <= 6
    assert 0.0 <= metrics.size_diversity <= 1.0
    assert 0.0 <= metrics.habitat_score <= 1.0
    assert "evidence" in metrics.to_dict()


def test_guilds_return_suitability_and_relative_index(tmp_path: Path) -> None:
    """Every guild returns a bounded suitability and a relative index."""
    dataset = make_dataset(tmp_path)
    metrics = habitat_metrics(dataset.trees, dataset.terrain)
    results = [guild_habitat(metrics, guild) for guild in GUILDS]
    assert len(results) == len(GUILDS)
    assert all(0.0 <= result.suitability <= 1.0 for result in results)
    assert all(result.relative_abundance_index >= 0.0 for result in results)
    assert "relative_abundance_index" in results[0].to_dict()


def test_bird_report_has_metrics_and_guilds(tmp_path: Path) -> None:
    """The bird report includes metrics, guilds, and the non-density caveat."""
    dataset = make_dataset(tmp_path)
    payload = bird_report(dataset.trees, dataset.terrain)
    metrics = payload["metrics"]
    guilds = payload["guilds"]
    assert isinstance(metrics, dict)
    assert isinstance(guilds, list)
    assert metrics["tree_count"] > 0
    assert len(guilds) == len(GUILDS)
    assert "not a density" in str(payload["caveat"])


def test_observation_loader(tmp_path: Path) -> None:
    """Optional observation CSV rows parse into observations."""
    path = tmp_path / "birds.csv"
    path.write_text(
        "species,lon,lat,count,guild\nRobin,-123.2,49.2,3,ground_foragers\n", encoding="utf-8"
    )
    observations = load_observations_csv(path)
    assert len(observations) == 1
    assert observations[0].species == "Robin"
    assert observations[0].count == 3.0
