"""Scenario application and annual tree-level projection.

An edit is applied to a copy of the baseline population, then every live tree is grown one
year at a time. Metrics are recorded at year zero and after each annual step so the web UI
can show a trajectory rather than a single end state.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from fresh_urban_forest.allometry import (
    estimate_crown_width_m,
    estimate_height_m,
    grow_tree,
    is_native_species,
    profile_for,
    species_group,
)
from fresh_urban_forest.metrics import compute_metrics
from fresh_urban_forest.models import (
    CanopyMetrics,
    Scenario,
    ScenarioEdit,
    ScenarioResult,
    TerrainGrid,
    TreeRecord,
    UrbanForestDataset,
)
from fresh_urban_forest.terrain import project_lonlat, sample_terrain_grid

PLANTING_COST_CAD = 750.0
REMOVAL_COST_CAD = 450.0
REPLACEMENT_COST_CAD = 1_100.0
MAINTENANCE_COST_CAD_PER_TREE_YEAR = 18.0


def area_ha(bounds: tuple[float, float, float, float]) -> float:
    """Calculate area in hectares from projected bounds.

    Parameters
    ----------
    bounds : tuple of float
        ``(left, bottom, right, top)`` in metres.

    Returns
    -------
    float
        Area in hectares, with a floor of 0.01.
    """
    return max((bounds[2] - bounds[0]) * (bounds[3] - bounds[1]) / 10_000.0, 0.01)


def apply_edits(
    trees: Sequence[TreeRecord],
    edits: Sequence[ScenarioEdit],
    terrain: TerrainGrid,
) -> tuple[TreeRecord, ...]:
    """Apply scenario edits in order to a tree population.

    Parameters
    ----------
    trees : sequence of TreeRecord
        Baseline population.
    edits : sequence of ScenarioEdit
        Edits to apply.
    terrain : TerrainGrid
        Terrain used to locate planted and moved trees.

    Returns
    -------
    tuple of TreeRecord
        The edited population.
    """
    population: dict[str, TreeRecord] = {tree.tree_id: tree for tree in trees}
    for edit in edits:
        if edit.kind == "plant":
            population[edit.tree_id] = _new_tree(edit, terrain)
        elif edit.kind == "remove":
            if edit.tree_id in population:
                population[edit.tree_id] = replace(population[edit.tree_id], status="removed")
        elif edit.kind == "replace":
            previous = population.get(edit.tree_id)
            replacement = _new_tree(edit, terrain, previous=previous)
            population[edit.tree_id] = replacement
        elif edit.kind == "move":
            previous = population.get(edit.tree_id)
            if previous is not None and edit.lon is not None and edit.lat is not None:
                x, y = project_lonlat(edit.lon, edit.lat, terrain.crs)
                elevation, _, _ = sample_terrain_grid(terrain, edit.lon, edit.lat)
                population[edit.tree_id] = replace(
                    previous,
                    lon=edit.lon,
                    lat=edit.lat,
                    x_m=x,
                    y_m=y,
                    elevation_m=elevation,
                )
    return tuple(population.values())


def project_scenario(
    dataset: UrbanForestDataset,
    scenario: Scenario,
    *,
    competition: float = 1.0,
    climate: float = 1.0,
) -> ScenarioResult:
    """Apply a scenario and project it forward year by year.

    Parameters
    ----------
    dataset : UrbanForestDataset
        Baseline dataset.
    scenario : Scenario
        Scenario to project.
    competition : float
        Competition multiplier for annual growth.
    climate : float
        Site-productivity multiplier for annual growth.

    Returns
    -------
    ScenarioResult
        Metrics for every year, final trees, cost, and score.
    """
    projected = apply_edits(dataset.trees, scenario.edits, dataset.terrain)
    hectares = area_ha(dataset.manifest.bounds)
    tree_only_baseline = compute_metrics(projected, area_ha=hectares)
    cover_offset = dataset.manifest.metrics.canopy_cover_pct - tree_only_baseline.canopy_cover_pct
    volume_offset = dataset.manifest.metrics.canopy_volume_m3 - tree_only_baseline.canopy_volume_m3

    def metrics(trees: Sequence[TreeRecord]) -> CanopyMetrics:
        return compute_metrics(
            trees,
            area_ha=hectares,
            cover_offset=cover_offset,
            volume_offset=volume_offset,
        )

    timeline: list[tuple[int, CanopyMetrics]] = []
    baseline_metrics = metrics(projected)
    timeline.append((0, baseline_metrics))
    current = projected
    for year in range(1, max(0, scenario.years) + 1):
        current = tuple(
            grow_tree(
                tree,
                1,
                competition=competition * competition_for_tree(tree),
            )
            if tree.status not in {"removed", "dead"}
            else tree
            for tree in current
        )
        timeline.append((year, metrics(current)))
    cost = scenario_cost(scenario)
    score = score_projection(
        baseline_metrics,
        timeline[-1][1],
        cost=cost,
        budget=250_000.0,
    )
    notes = (
        "Growth is a transparent urban allometric model, not a calibrated FVS projection.",
        "Canopy volume and carbon are above-ground estimates from diameter allometry.",
        "Year-zero cover uses crown geometry so every year uses the same method.",
    )
    return ScenarioResult(
        scenario=scenario,
        metrics_by_year=tuple(timeline),
        final_trees=current,
        cost=round(cost, 2),
        score=round(score, 2),
        notes=notes,
    )


def competition_for_tree(tree: TreeRecord) -> float:
    """Derive a competition multiplier from crown-light-exposure attributes.

    Parameters
    ----------
    tree : TreeRecord
        Tree whose attributes may include ``crown_light_exposure``.

    Returns
    -------
    float
        A multiplier between 0.75 and 1.10. Trees with no recorded exposure use 1.0.
    """
    raw = tree.attributes.get("crown_light_exposure", "")
    try:
        exposure = int(float(str(raw).strip()))
    except (TypeError, ValueError):
        return 1.0
    if 0 <= exposure <= 5:
        return 0.75 + 0.07 * exposure
    return 1.0


def scenario_cost(scenario: Scenario) -> float:
    """Estimate the implementation cost of a scenario.

    Parameters
    ----------
    scenario : Scenario
        Scenario with edits.

    Returns
    -------
    float
        Cost in Canadian dollars, including a maintenance allowance.
    """
    plants = sum(1 for edit in scenario.edits if edit.kind == "plant")
    removals = sum(1 for edit in scenario.edits if edit.kind == "remove")
    replacements = sum(1 for edit in scenario.edits if edit.kind == "replace")
    moves = sum(1 for edit in scenario.edits if edit.kind == "move")
    establishment = (
        plants * PLANTING_COST_CAD
        + removals * REMOVAL_COST_CAD
        + replacements * REPLACEMENT_COST_CAD
        + moves * 250.0
    )
    maintenance = plants * MAINTENANCE_COST_CAD_PER_TREE_YEAR * max(0, scenario.years)
    return establishment + maintenance


def score_projection(
    baseline: CanopyMetrics,
    final: CanopyMetrics,
    *,
    cost: float,
    budget: float,
) -> float:
    """Score a projected scenario against baseline and planning targets.

    Parameters
    ----------
    baseline : CanopyMetrics
        Baseline metrics.
    final : CanopyMetrics
        Final-year metrics.
    cost : float
        Scenario cost in Canadian dollars.
    budget : float
        Planning budget in Canadian dollars.

    Returns
    -------
    float
        A score from zero to one hundred. Higher is better.
    """
    cover = min(1.0, final.canopy_cover_pct / 30.0)
    native = min(1.0, final.native_fraction / 0.40)
    diversity = min(1.0, final.shannon_index / 2.2)
    carbon_retention = min(1.2, final.total_carbon_kg / max(baseline.total_carbon_kg, 1.0))
    cost_penalty = min(0.35, cost / max(budget, 1.0) * 0.35)
    raw = 0.40 * cover + 0.25 * native + 0.20 * diversity + 0.15 * (carbon_retention / 1.2)
    return max(0.0, min(100.0, 100.0 * (raw - cost_penalty)))


def scenario_summary(result: ScenarioResult) -> dict[str, object]:
    """Build a compact JSON-safe summary for the API and CLI.

    Parameters
    ----------
    result : ScenarioResult
        Result to summarise.

    Returns
    -------
    dict
        Baseline, final, delta, cost, score, and timeline values.
    """
    baseline = result.metrics_by_year[0][1]
    final = result.metrics_by_year[-1][1]
    return {
        "scenario_id": result.scenario.scenario_id,
        "name": result.scenario.name,
        "years": result.scenario.years,
        "revision": result.scenario.revision,
        "cost_cad": result.cost,
        "score": result.score,
        "baseline": _metrics_dict(baseline),
        "final": _metrics_dict(final),
        "timeline": [
            {"year": year, **_metrics_dict(metrics)} for year, metrics in result.metrics_by_year
        ],
        "notes": list(result.notes),
    }


def _new_tree(
    edit: ScenarioEdit,
    terrain: TerrainGrid,
    *,
    previous: TreeRecord | None = None,
) -> TreeRecord:
    """Create a planted or replacement tree from an edit.

    Parameters
    ----------
    edit : ScenarioEdit
        The plant or replace edit.
    terrain : TerrainGrid
        Terrain used for coordinates and elevation.
    previous : TreeRecord or None
        Existing tree for a replacement.

    Returns
    -------
    TreeRecord
        New tree record.
    """
    lon = edit.lon if edit.lon is not None else (previous.lon if previous else 0.0)
    lat = edit.lat if edit.lat is not None else (previous.lat if previous else 0.0)
    species = edit.species or (previous.species if previous else "Unknown")
    group = species_group(species)
    dbh = edit.dbh_cm or (5.0 if previous is None else 8.0)
    height = edit.height_m or estimate_height_m(dbh, group)
    crown = edit.crown_width_m or estimate_crown_width_m(dbh, group)
    x, y = project_lonlat(lon, lat, terrain.crs)
    elevation, _, _ = sample_terrain_grid(terrain, lon, lat)
    return TreeRecord(
        tree_id=edit.tree_id,
        lon=lon,
        lat=lat,
        species=species,
        common_name=edit.common_name or species,
        genus=species.split()[0] if species else "",
        dbh_cm=round(float(dbh), 2),
        height_m=round(float(height), 2),
        crown_width_m=round(float(crown), 2),
        crown_ratio=profile_for(species).crown_ratio,
        status="planted",
        source="scenario",
        source_date=None,
        native=is_native_species(species),
        x_m=round(x, 3),
        y_m=round(y, 3),
        elevation_m=round(elevation, 2),
        lidar_height_m=0.0,
        attributes={"note": edit.note, "edit_id": edit.edit_id},
    )


def _metrics_dict(metrics: CanopyMetrics) -> dict[str, object]:
    """Convert metrics to a compact dictionary.

    Parameters
    ----------
    metrics : CanopyMetrics
        Metrics to convert.

    Returns
    -------
    dict
        JSON-safe values.
    """
    return {
        "tree_count": metrics.tree_count,
        "species_count": metrics.species_count,
        "native_fraction": metrics.native_fraction,
        "canopy_cover_pct": metrics.canopy_cover_pct,
        "canopy_volume_m3": metrics.canopy_volume_m3,
        "mean_height_m": metrics.mean_height_m,
        "p95_height_m": metrics.p95_height_m,
        "total_carbon_kg": metrics.total_carbon_kg,
        "shannon_index": metrics.shannon_index,
    }
