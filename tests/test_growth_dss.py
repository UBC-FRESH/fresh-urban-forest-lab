"""Tests for scenario editing, projection, and decision support."""

from __future__ import annotations

import json
from pathlib import Path

from fresh_urban_forest.dataset import dataset_summary, load_dataset
from fresh_urban_forest.dss import (
    candidates_to_edits,
    compare_scenarios,
    export_scenario_csv,
    export_scenario_geojson,
    metric_delta,
    recommend_planting,
)
from fresh_urban_forest.growth import (
    apply_edits,
    competition_for_tree,
    project_scenario,
    scenario_cost,
    scenario_summary,
    score_projection,
)
from fresh_urban_forest.models import Scenario, ScenarioEdit, TreeRecord
from fresh_urban_forest.scene import build_scene, distance_m, scene_bounds_local
from tests.fixtures import make_dataset


def _edit(kind: str, tree_id: str, **kwargs: object) -> ScenarioEdit:
    """Build a scenario edit with defaults."""
    return ScenarioEdit(edit_id=f"e-{tree_id}-{kind}", kind=kind, tree_id=tree_id, **kwargs)  # type: ignore[arg-type]


def test_apply_edits_plants_removes_replaces_and_moves(tmp_path: Path) -> None:
    """Every edit kind changes the population in the expected way."""
    dataset = make_dataset(tmp_path)
    first = dataset.trees[0]
    edits = [
        _edit("remove", first.tree_id),
        _edit(
            "plant",
            "plant:1",
            lon=first.lon,
            lat=first.lat,
            species="Acer macrophyllum",
            dbh_cm=6.0,
            height_m=4.0,
        ),
        _edit(
            "replace",
            dataset.trees[1].tree_id,
            lon=dataset.trees[1].lon,
            lat=dataset.trees[1].lat,
            species="Quercus rubra",
            dbh_cm=8.0,
        ),
        _edit("move", dataset.trees[2].tree_id, lon=dataset.trees[2].lon, lat=dataset.trees[2].lat),
    ]
    population = apply_edits(dataset.trees, edits, dataset.terrain)
    by_id = {tree.tree_id: tree for tree in population}
    assert by_id[first.tree_id].status == "removed"
    assert by_id["plant:1"].status == "planted"
    assert by_id[dataset.trees[1].tree_id].species == "Quercus rubra"
    assert by_id[dataset.trees[2].tree_id].x_m is not None


def test_scenario_projection_produces_a_timeline_and_cost(tmp_path: Path) -> None:
    """A projection records year zero plus one metric snapshot per year."""
    dataset = make_dataset(tmp_path)
    scenario = Scenario(
        scenario_id="s1",
        name="Plant ten",
        created_utc="2026-11-03T00:00:00Z",
        base_dataset_id=dataset.manifest.dataset_id,
        years=5,
        edits=tuple(
            _edit(
                "plant",
                f"plant:{index}",
                lon=dataset.trees[index].lon,
                lat=dataset.trees[index].lat,
                species="Acer macrophyllum",
                dbh_cm=6.0,
            )
            for index in range(3)
        ),
    )
    result = project_scenario(dataset, scenario)
    assert len(result.metrics_by_year) == 6
    assert result.metrics_by_year[0][1].tree_count >= dataset.manifest.metrics.tree_count
    assert (
        result.metrics_by_year[-1][1].canopy_cover_pct
        >= result.metrics_by_year[0][1].canopy_cover_pct
    )
    assert result.cost > 0
    assert 0 <= result.score <= 100
    summary = scenario_summary(result)
    assert summary["scenario_id"] == "s1"
    timeline = summary["timeline"]
    assert isinstance(timeline, list)
    assert len(timeline) == 6
    assert scenario_cost(scenario) > 0


def test_score_and_competition_helpers() -> None:
    """Scores stay bounded and crown-light exposure becomes a growth multiplier."""
    tree = TreeRecord(
        tree_id="t",
        lon=0.0,
        lat=0.0,
        attributes={"crown_light_exposure": "5"},
    )
    assert competition_for_tree(tree) == 1.10
    assert competition_for_tree(TreeRecord(tree_id="x", lon=0.0, lat=0.0)) == 1.0
    assert (
        competition_for_tree(
            TreeRecord(tree_id="x", lon=0.0, lat=0.0, attributes={"crown_light_exposure": "x"})
        )
        == 1.0
    )
    from fresh_urban_forest.metrics import compute_metrics

    baseline = compute_metrics(
        [TreeRecord(tree_id="b", lon=0.0, lat=0.0, dbh_cm=10.0)], area_ha=1.0
    )
    final = compute_metrics([TreeRecord(tree_id="b", lon=0.0, lat=0.0, dbh_cm=20.0)], area_ha=1.0)
    assert 0 <= score_projection(baseline, final, cost=1000.0, budget=10000.0) <= 100


def test_planting_candidates_and_exports(tmp_path: Path) -> None:
    """The recommender ranks open cells and exports produce usable files."""
    dataset = make_dataset(tmp_path)
    candidates = recommend_planting(dataset, count=5, species="Acer macrophyllum", grid_m=10.0)
    assert candidates
    assert candidates[0].score >= candidates[-1].score
    edits = candidates_to_edits(candidates, species="Acer macrophyllum")
    assert len(edits) == len(candidates)
    assert all(edit.kind == "plant" for edit in edits)
    budgeted = recommend_planting(dataset, count=100, budget_cad=1500.0)
    assert len(budgeted) <= 2
    assert recommend_planting(dataset, count=0) == ()
    center = candidates[0]
    local = recommend_planting(
        dataset,
        count=5,
        grid_m=10.0,
        center_lonlat=(center.lon, center.lat),
        radius_m=25.0,
    )
    assert local
    from fresh_urban_forest.terrain import project_lonlat

    cx, cy = project_lonlat(center.lon, center.lat, dataset.terrain.crs)
    for candidate in local:
        x, y = project_lonlat(candidate.lon, candidate.lat, dataset.terrain.crs)
        assert ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 <= 25.0 + 1.0
    scenario = Scenario(
        scenario_id="s",
        name="s",
        created_utc="now",
        base_dataset_id=dataset.manifest.dataset_id,
        years=2,
        edits=edits,
    )
    result = project_scenario(dataset, scenario)
    csv_path = export_scenario_csv(result, tmp_path / "out.csv")
    assert csv_path.read_text().startswith("year,")
    geojson_path = export_scenario_geojson(result, tmp_path / "out.geojson")
    payload = json.loads(geojson_path.read_text())
    assert payload["type"] == "FeatureCollection"
    comparison = compare_scenarios([result])
    assert comparison.best_scenario_id == "s"
    delta = metric_delta(result.metrics_by_year[0][1], result.metrics_by_year[-1][1])
    assert "canopy_cover_pct" in delta


def test_dataset_round_trip_and_scene(tmp_path: Path) -> None:
    """A written dataset loads back and builds a scene payload."""
    dataset = make_dataset(tmp_path)
    loaded = load_dataset(tmp_path / "dataset")
    assert loaded.manifest.dataset_id == dataset.manifest.dataset_id
    assert len(loaded.trees) == len(dataset.trees)
    summary = dataset_summary(loaded)
    assert summary["tree_count"] == len(loaded.trees)
    scene = build_scene(loaded)
    scene_trees = scene["trees"]
    terrain = scene["terrain"]
    assert isinstance(scene_trees, list)
    assert len(scene_trees) == len(loaded.trees)
    assert isinstance(terrain, dict)
    assert terrain["width"] == loaded.terrain.width
    assert "bounds_wgs84" in scene
    corners = scene["corners_wgs84"]
    assert isinstance(corners, list)
    assert len(corners) == 4
    buildings = scene["buildings"]
    assert isinstance(buildings, list)
    assert buildings
    assert "base_z" in buildings[0]
    assert scene_bounds_local(loaded)[2] > 0
    first, second = loaded.trees[0], loaded.trees[1]
    assert distance_m(first, second) >= 0
    assert distance_m(TreeRecord(tree_id="x", lon=0.0, lat=0.0), second) == float("inf")
