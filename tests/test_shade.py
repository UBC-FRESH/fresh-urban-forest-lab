"""Tests for time-integrated shade accounting."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fresh_urban_forest.shade import (
    default_step_hours,
    shade_at_tree,
    shade_period,
    shade_png,
    write_shade_product,
)
from tests.fixtures import make_dataset


def _whens() -> tuple[dt.datetime, ...]:
    """Return three daytime samples in local Pacific daylight time."""
    zone = dt.timezone(dt.timedelta(hours=-7))
    return tuple(dt.datetime(2026, 6, 21, hour, 0, tzinfo=zone) for hour in (9, 12, 15))


def test_step_hours_uses_the_median_interval() -> None:
    """A regular day is represented by its sample interval."""
    assert default_step_hours(_whens()) == pytest.approx(3.0)
    assert default_step_hours((_whens()[0],)) == 1.0


def test_shade_period_conserves_sunlit_and_shade(tmp_path: Path) -> None:
    """Sunlit and combined shade cover the daylight sample exactly."""
    dataset = make_dataset(tmp_path)
    period = shade_period(dataset, _whens(), include_terrain=False)
    metrics = period.metrics
    assert metrics["sunlit_fraction"] + metrics["shade_fraction"] == pytest.approx(1.0)
    assert metrics["building_shade_fraction"] + metrics["tree_shade_fraction"] - metrics[
        "overlap_fraction"
    ] == pytest.approx(metrics["shade_fraction"])
    assert period.daylight_samples == 3
    assert period.daylight_sampled_hours == pytest.approx(9.0)


def test_shade_period_tracks_marginal_tree_shade(tmp_path: Path) -> None:
    """A selected tree has a positive marginal contribution no larger than all tree shade."""
    dataset = make_dataset(tmp_path)
    period = shade_period(
        dataset, _whens(), include_terrain=False, tree_id=dataset.trees[1].tree_id
    )
    assert period.metrics["marginal_tree_shade_fraction"] > 0.0
    assert period.metrics["marginal_tree_shade_fraction"] <= period.metrics["tree_shade_fraction"]


def test_shade_at_tree_returns_a_card(tmp_path: Path) -> None:
    """The tree card returns a positive shade efficiency and evidence."""
    dataset = make_dataset(tmp_path)
    card = shade_at_tree(dataset, dataset.trees[1], _whens(), include_terrain=False)
    assert float(str(card["shade_efficiency_m2h_per_m3"])) > 0.0
    assert 0.0 <= float(str(card["sun_fraction_at_base"])) <= 1.0
    assert "evidence" in card


def test_shade_png_and_product_writer(tmp_path: Path) -> None:
    """The aggregate PNG and product writer produce files."""
    dataset = make_dataset(tmp_path)
    period = shade_period(dataset, _whens(), include_terrain=False)
    assert shade_png(period).startswith(b"\x89PNG")
    path = write_shade_product(period, tmp_path / "shade")
    assert path.exists()
    assert (tmp_path / "shade" / "shade.png").exists()
    assert (tmp_path / "shade" / "shade.npz").exists()
