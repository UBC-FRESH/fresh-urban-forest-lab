"""Tests for baseline-versus-scenario site shade evaluation."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import cast

import pytest

from fresh_urban_forest.site_scenario import CandidateSite, SiteScenario, build_site_scenario
from fresh_urban_forest.site_shade import evaluate_site_scenario
from fresh_urban_forest.terrain import unproject_xy
from tests.fixtures import CRS, make_dataset


def _whens() -> tuple[dt.datetime, ...]:
    """Return three daytime samples in local Pacific daylight time."""
    zone = dt.timezone(dt.timedelta(hours=-7))
    return tuple(dt.datetime(2026, 6, 21, hour, 0, tzinfo=zone) for hour in (9, 12, 15))


def _candidate(site_id: str, x: float, y: float) -> CandidateSite:
    """Build a candidate at a projected test-grid point."""
    lon, lat = unproject_xy(x, y, CRS)
    return CandidateSite(
        site_id=site_id,
        cell_id="r00c00",
        lon=lon,
        lat=lat,
        area_m2=100.0,
        street_adjacent=False,
        action_class="plant_cool",
        action_label="plant + cool",
        opportunity_tier="high",
    )


def _scenario(candidates: dict[str, CandidateSite]) -> SiteScenario:
    """Build a two-site scenario."""
    sites = [
        {
            "site_id": site_id,
            "species": "Acer rubrum",
            "height_m": 8.0,
            "crown_radius_m": 3.0,
            "count": 1,
            "cost_cad": 850.0,
            "water_l_per_year": 1200.0,
            "maintenance": "establishment only",
            "assumption_source": "explicit test input",
        }
        for site_id in candidates
    ]
    return build_site_scenario(
        label="Two-site test",
        sites=sites,
        settings={"target_height_m": 1.5},
        candidate_ids=set(candidates),
    )


def test_evaluate_site_scenario_reports_baseline_deltas_and_sensitivity(tmp_path: Path) -> None:
    """The baseline and scenario use the same samples and report site deltas."""
    dataset = make_dataset(tmp_path)
    candidates = {
        "site-a": _candidate("site-a", 10.0, 90.0),
        "site-b": _candidate("site-b", 90.0, 10.0),
    }
    scenario = _scenario(candidates)
    evaluation = evaluate_site_scenario(
        dataset,
        scenario,
        candidates,
        _whens(),
        include_per_site=True,
        include_sensitivity=True,
    )
    assert evaluation.method == "projected-shadow-accumulation-combined"
    assert evaluation.scenario_shade_m2h >= evaluation.baseline_shade_m2h
    assert evaluation.delta_shade_m2h >= 0.0
    assert len(evaluation.per_site) == 2
    assert all(site.delta_shade_m2h >= 0.0 for site in evaluation.per_site)
    assert len(evaluation.sensitivity) == 4
    assert {case.case for case in evaluation.sensitivity} == {
        "height_minus_20pct",
        "height_plus_20pct",
        "crown_minus_20pct",
        "crown_plus_20pct",
    }
    assert evaluation.settings["target_height_m"] == 1.5
    assert evaluation.settings["tree_count"] == 2
    assert evaluation.uncertainty["p45_citywide_change"] == (
        "unresolved; do not infer a citywide net direction"
    )
    payload = evaluation.to_dict()
    assert payload["scenario_id"] == scenario.scenario_id
    assert len(cast("list[object]", payload["per_site"])) == 2
    assert "evidence" in payload


def test_evaluate_site_scenario_can_skip_optional_work(tmp_path: Path) -> None:
    """Per-site and sensitivity work are optional and explicit."""
    dataset = make_dataset(tmp_path)
    candidates = {"site-a": _candidate("site-a", 10.0, 90.0)}
    scenario = _scenario(candidates)
    evaluation = evaluate_site_scenario(
        dataset,
        scenario,
        candidates,
        _whens()[:1],
        include_per_site=False,
        include_sensitivity=False,
    )
    assert evaluation.per_site == ()
    assert evaluation.sensitivity == ()
    assert evaluation.settings["site_count"] == 1
    assert evaluation.baseline_shade_fraction + evaluation.scenario_shade_fraction >= 0.0


def test_evaluate_site_scenario_rejects_missing_candidate_and_empty_times(
    tmp_path: Path,
) -> None:
    """Missing candidates and empty sample lists are explicit errors."""
    dataset = make_dataset(tmp_path)
    candidate = _candidate("site-a", 10.0, 90.0)
    scenario = _scenario({"site-a": candidate})
    with pytest.raises(ValueError, match="at least one sample"):
        evaluate_site_scenario(dataset, scenario, {"site-a": candidate}, ())
    with pytest.raises(ValueError, match="no candidate"):
        evaluate_site_scenario(dataset, scenario, {}, _whens())
