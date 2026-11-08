"""Tests for candidate sites and explicit site-level scenario contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import numpy as np
import pytest

from fresh_urban_forest.planting_opportunity import GAP_EVIDENCE, GapMasks
from fresh_urban_forest.site_scenario import (
    SITE_CANDIDATES_SCHEMA_VERSION,
    SITE_SCENARIO_SCHEMA_VERSION,
    build_site_scenario,
    candidate_sites_document,
    candidate_sites_geojson,
    extract_candidate_sites,
    normalize_site_scenario,
    scenario_totals,
    write_candidate_site_product,
)

BOUNDS = (493_000.0, 5_455_000.0, 493_800.0, 5_455_800.0)


def _masks() -> GapMasks:
    """Build two gap components in adjacent 400 m cells."""
    shape = (80, 80)
    gap = np.zeros(shape, dtype=np.bool_)
    street = np.zeros(shape, dtype=np.bool_)
    gap[5:10, 5:10] = True
    street[5:7, 5:7] = True
    gap[60:64, 55:60] = True
    return GapMasks(
        open_ground=gap,
        gap=gap,
        street_gap=street,
        interior_open=np.zeros(shape, dtype=np.bool_),
        slope_deg=np.zeros(shape, dtype=np.float32),
        summary={},
        evidence=GAP_EVIDENCE,
    )


def _actions() -> dict[str, dict[str, object]]:
    """Return action context for the two cells."""
    return {
        "r00c00": {
            "action_class": "plant_cool",
            "action_label": "plant + cool",
            "opportunity_tier": "high",
        },
        "r01c01": {
            "action_class": "monitor",
            "action_label": "monitor",
            "opportunity_tier": "low",
        },
    }


def test_extract_candidate_sites_is_deterministic_and_joins_actions() -> None:
    """Components become stable sites with context and no ownership fields."""
    sites = extract_candidate_sites(
        _masks(), bounds=BOUNDS, crs="EPSG:3157", action_cells=_actions()
    )
    assert len(sites) == 2
    first = sites[0]
    assert first.site_id == "gap-r00c00-0001"
    assert first.cell_id == "r00c00"
    assert first.action_class == "plant_cool"
    assert first.action_label == "plant + cool"
    assert first.opportunity_tier == "high"
    assert first.street_adjacent is True
    assert first.area_m2 == pytest.approx(2500.0)
    assert sites[1].action_class == "monitor"
    assert sites[1].street_adjacent is False
    assert -180.0 <= first.lon <= 180.0
    assert -90.0 <= first.lat <= 90.0
    again = extract_candidate_sites(
        _masks(), bounds=BOUNDS, crs="EPSG:3157", action_cells=_actions()
    )
    assert [site.to_dict() for site in again] == [site.to_dict() for site in sites]
    payload = first.to_dict()
    assert "owner" not in payload
    assert "address" not in payload


def test_extract_candidate_sites_caps_and_rejects_invalid_thresholds() -> None:
    """Small areas and per-cell caps are respected."""
    limited = extract_candidate_sites(
        _masks(),
        bounds=BOUNDS,
        crs="EPSG:3157",
        action_cells=_actions(),
        site_min_area_m2=5000.0,
    )
    assert limited == ()
    capped = extract_candidate_sites(
        _masks(),
        bounds=BOUNDS,
        crs="EPSG:3157",
        action_cells=_actions(),
        max_sites=1,
    )
    assert len(capped) == 1
    assert capped[0].action_class == "plant_cool"
    with pytest.raises(ValueError, match="positive"):
        extract_candidate_sites(_masks(), bounds=BOUNDS, crs="EPSG:3157", site_min_area_m2=0.0)
    with pytest.raises(ValueError, match="positive"):
        extract_candidate_sites(_masks(), bounds=BOUNDS, crs="EPSG:3157", max_sites=0)


def test_candidate_documents_and_writer(tmp_path: Path) -> None:
    """Candidate documents and GeoJSON carry the expected schema."""
    sites = extract_candidate_sites(
        _masks(), bounds=BOUNDS, crs="EPSG:3157", action_cells=_actions()
    )
    metadata = {"dataset_id": "test", "thresholds": {"site_min_area_m2": 45.0}}
    document = candidate_sites_document(sites, metadata=metadata)
    collection = candidate_sites_geojson(sites, metadata=metadata)
    assert document["schema_version"] == SITE_CANDIDATES_SCHEMA_VERSION
    assert len(cast("list[object]", document["sites"])) == 2
    assert collection["type"] == "FeatureCollection"
    assert len(cast("list[object]", collection["features"])) == 2
    paths = write_candidate_site_product(sites, tmp_path, metadata=metadata)
    assert paths["json"].exists()
    assert paths["geojson"].exists()
    written = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert written["schema_version"] == SITE_CANDIDATES_SCHEMA_VERSION
    assert len(written["sites"]) == 2


def _site(site_id: str = "gap-r00c00-0001", **overrides: object) -> dict[str, object]:
    """Return a valid scenario-site mapping."""
    site: dict[str, object] = {
        "site_id": site_id,
        "species": "Acer rubrum",
        "height_m": 6.0,
        "crown_radius_m": 2.5,
        "count": 2,
        "cost_cad": 850.0,
        "water_l_per_year": 1200.0,
        "maintenance": "establishment only",
        "assumption_source": "explicit test input",
    }
    site.update(overrides)
    return site


def _scenario(**overrides: object) -> dict[str, object]:
    """Return a valid scenario document."""
    payload: dict[str, object] = {
        "schema_version": SITE_SCENARIO_SCHEMA_VERSION,
        "scenario_id": "scenario-test",
        "label": "Test scenario",
        "created_at": "2026-11-08T00:00:00+00:00",
        "settings": {"date": "2026-06-21", "time": "12:00"},
        "sites": [_site()],
        "uncertainty": {"method": "test"},
    }
    payload.update(overrides)
    return payload


def test_scenario_normalization_and_round_trip() -> None:
    """A valid scenario derives totals and survives a round trip."""
    scenario = normalize_site_scenario(_scenario(), candidate_ids={"gap-r00c00-0001"})
    assert scenario.totals["sites"] == 1
    assert scenario.totals["trees"] == 2
    assert scenario.totals["cost_cad"] == pytest.approx(1700.0)
    assert scenario.totals["water_l_per_year"] == pytest.approx(2400.0)
    round_trip = normalize_site_scenario(scenario.to_dict())
    assert round_trip.to_dict() == scenario.to_dict()
    built = build_site_scenario(label="Built", sites=[_site()])
    assert built.scenario_id.startswith("scenario-")
    assert built.totals["trees"] == 2
    assert scenario_totals(built.sites)["sites"] == 1


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"schema_version": "wrong"}, "schema_version"),
        ({"sites": [_site(), _site()]}, "duplicate"),
        ({"sites": [_site("not-a-candidate")]}, "unknown candidate"),
        ({"sites": [_site(count=0)]}, "count"),
        ({"sites": [_site(height_m=0.1)]}, "height_m"),
        ({"sites": [_site(crown_radius_m=50.0)]}, "crown_radius_m"),
        ({"sites": [_site(cost_cad=-1.0)]}, "cost_cad"),
        ({"sites": [_site(site_id="")]}, "site_id"),
    ],
)
def test_scenario_validation_rejects_bad_fields(overrides: dict[str, object], message: str) -> None:
    """Malformed fields and candidate mismatches are explicit errors."""
    payload = _scenario(**overrides)
    with pytest.raises(ValueError, match=message):
        normalize_site_scenario(payload, candidate_ids={"gap-r00c00-0001"})


def test_scenario_limits_and_empty_state() -> None:
    """The scenario cap and total-tree cap are enforced; empty is explicit."""
    empty = normalize_site_scenario(_scenario(sites=[]))
    assert empty.totals["trees"] == 0
    too_many = _scenario(sites=[_site(f"gap-r00c00-{index:04d}") for index in range(201)])
    with pytest.raises(ValueError, match="at most 200"):
        normalize_site_scenario(too_many)
    too_many_trees = _scenario(
        sites=[_site(f"gap-r00c00-{index:04d}", count=50) for index in range(21)]
    )
    with pytest.raises(ValueError, match="at most 1000 trees"):
        normalize_site_scenario(too_many_trees)
