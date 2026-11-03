"""Decision-support helpers: planting candidates, scenario comparison, and exports.

The recommender is intentionally explainable. It ranks open, low-canopy cells that are
near existing trees, outside buildings, and inside the analysis boundary. Every candidate
carries the reasons for its rank, so a planner can disagree with the model rather than
guess at it.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from shapely.geometry import Point, Polygon

from fresh_urban_forest.allometry import (
    estimate_crown_width_m,
    estimate_height_m,
    is_native_species,
)
from fresh_urban_forest.growth import PLANTING_COST_CAD
from fresh_urban_forest.models import (
    CanopyMetrics,
    ScenarioEdit,
    ScenarioResult,
    TerrainGrid,
    UrbanForestDataset,
)
from fresh_urban_forest.terrain import grid_cell_center, project_lonlat


@dataclass(frozen=True, slots=True)
class PlantingCandidate:
    """One potential planting site with its evidence.

    Attributes
    ----------
    lon : float
        Longitude.
    lat : float
        Latitude.
    score : float
        Ranking score, higher is better.
    canopy_height_m : float
        Existing canopy height at the site.
    slope_percent : float
        Terrain slope.
    nearest_tree_m : float
        Distance to the nearest existing tree.
    reasons : tuple of str
        Human-readable ranking reasons.
    """

    lon: float
    lat: float
    score: float
    canopy_height_m: float
    slope_percent: float
    nearest_tree_m: float
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScenarioComparison:
    """A side-by-side comparison of projected scenarios.

    Attributes
    ----------
    scenarios : tuple of ScenarioResult
        Results in input order.
    ranking : tuple of tuple of str and float
        Scenario identifiers and scores, highest first.
    best_scenario_id : str
        Identifier of the highest-scoring scenario.
    """

    scenarios: tuple[ScenarioResult, ...]
    ranking: tuple[tuple[str, float], ...]
    best_scenario_id: str


def recommend_planting(
    dataset: UrbanForestDataset,
    *,
    count: int = 50,
    species: str = "Acer macrophyllum",
    budget_cad: float | None = None,
    grid_m: float = 8.0,
    max_slope_percent: float = 18.0,
) -> tuple[PlantingCandidate, ...]:
    """Rank open planting sites in a dataset.

    Parameters
    ----------
    dataset : UrbanForestDataset
        Dataset to search.
    count : int
        Maximum number of candidates.
    species : str
        Species proposed for the site, used in the native-species preference.
    budget_cad : float or None
        Optional budget cap. The number of candidates is reduced accordingly.
    grid_m : float
        Candidate grid spacing in metres.
    max_slope_percent : float
        Maximum slope allowed at a candidate.

    Returns
    -------
    tuple of PlantingCandidate
        Ranked candidates, best first.
    """
    if count <= 0 or grid_m <= 0:
        return ()
    if budget_cad is not None:
        count = min(count, max(0, int(budget_cad // PLANTING_COST_CAD)))
    if count == 0:
        return ()
    grid = dataset.terrain
    left, bottom, right, top = grid.bounds
    step = max(grid_m, 1.0)
    cols = max(1, int((right - left) // step))
    rows = max(1, int((top - bottom) // step))
    tree_xy = np.asarray(
        [
            (tree.x_m, tree.y_m)
            for tree in dataset.trees
            if tree.x_m is not None and tree.y_m is not None
        ],
        dtype=np.float64,
    )
    boundary = _boundary_polygon(dataset, grid.crs)
    buildings = [_building_polygon(building.rings, grid.crs) for building in dataset.buildings]
    native_preference = 1.15 if is_native_species(species) else 1.0
    candidates: list[PlantingCandidate] = []
    for row in range(rows):
        for col in range(cols):
            x, y = grid_cell_center(grid, min(row, grid.height - 1), min(col, grid.width - 1))
            if boundary is not None and not boundary.contains(Point(x, y)):
                continue
            elevation, canopy, slope = _grid_sample_xy(grid, x, y)
            if canopy >= 2.0 or slope > max_slope_percent:
                continue
            if any(polygon.contains(Point(x, y)) for polygon in buildings):
                continue
            nearest = _nearest_distance(tree_xy, x, y)
            if nearest < 3.0:
                continue
            connectivity = math.exp(-max(nearest - 5.0, 0.0) / 28.0)
            openness = 1.0 - min(canopy / 2.0, 1.0)
            slope_bonus = 1.0 - min(slope / max(max_slope_percent, 1e-9), 1.0)
            score = (0.50 * openness + 0.35 * connectivity + 0.15 * slope_bonus) * native_preference
            lon, lat = _unproject(x, y, grid.crs)
            reasons = (
                f"open canopy ({canopy:.1f} m)",
                f"{nearest:.0f} m from the nearest tree",
                f"{slope:.1f}% slope",
            )
            candidates.append(
                PlantingCandidate(
                    lon=lon,
                    lat=lat,
                    score=round(score, 4),
                    canopy_height_m=round(canopy, 2),
                    slope_percent=round(slope, 2),
                    nearest_tree_m=round(nearest, 2),
                    reasons=reasons,
                )
            )
            _ = elevation
    candidates.sort(key=lambda candidate: (-candidate.score, candidate.lat, candidate.lon))
    return tuple(candidates[:count])


def candidates_to_edits(
    candidates: Sequence[PlantingCandidate],
    *,
    species: str,
    common_name: str = "",
    dbh_cm: float = 6.0,
    id_prefix: str = "plant",
) -> tuple[ScenarioEdit, ...]:
    """Convert ranked candidates into plant edits.

    Parameters
    ----------
    candidates : sequence of PlantingCandidate
        Candidates to convert.
    species : str
        Species to plant.
    common_name : str
        Common name for the planted trees.
    dbh_cm : float
        Initial diameter.
    id_prefix : str
        Prefix for generated tree identifiers.

    Returns
    -------
    tuple of ScenarioEdit
        Plant edits.
    """
    edits = []
    for index, candidate in enumerate(candidates):
        edits.append(
            ScenarioEdit(
                edit_id=f"{id_prefix}-{index + 1}",
                kind="plant",
                tree_id=f"{id_prefix}:{index + 1}",
                lon=candidate.lon,
                lat=candidate.lat,
                species=species,
                common_name=common_name,
                dbh_cm=dbh_cm,
                height_m=estimate_height_m(dbh_cm, species),
                crown_width_m=estimate_crown_width_m(dbh_cm, species),
                note="; ".join(candidate.reasons),
            )
        )
    return tuple(edits)


def compare_scenarios(results: Sequence[ScenarioResult]) -> ScenarioComparison:
    """Rank projected scenarios by decision-support score.

    Parameters
    ----------
    results : sequence of ScenarioResult
        Results to compare.

    Returns
    -------
    ScenarioComparison
        Results, ranking, and the best scenario identifier.
    """
    ranking = tuple(
        sorted(
            ((result.scenario.scenario_id, result.score) for result in results),
            key=lambda item: (-item[1], item[0]),
        )
    )
    return ScenarioComparison(
        scenarios=tuple(results),
        ranking=ranking,
        best_scenario_id=ranking[0][0] if ranking else "",
    )


def export_scenario_csv(result: ScenarioResult, path: Path) -> Path:
    """Write a scenario timeline as CSV.

    Parameters
    ----------
    result : ScenarioResult
        Result to export.
    path : Path
        Destination CSV.

    Returns
    -------
    Path
        The written path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "year,tree_count,species_count,native_fraction,canopy_cover_pct,"
        "canopy_volume_m3,mean_height_m,p95_height_m,total_carbon_kg,shannon_index"
    ]
    for year, metrics in result.metrics_by_year:
        lines.append(
            f"{year},{metrics.tree_count},{metrics.species_count},{metrics.native_fraction:.4f},"
            f"{metrics.canopy_cover_pct:.3f},{metrics.canopy_volume_m3:.3f},"
            f"{metrics.mean_height_m:.3f},{metrics.p95_height_m:.3f},"
            f"{metrics.total_carbon_kg:.3f},{metrics.shannon_index:.4f}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def export_scenario_geojson(result: ScenarioResult, path: Path) -> Path:
    """Write the final tree population as GeoJSON.

    Parameters
    ----------
    result : ScenarioResult
        Result to export.
    path : Path
        Destination GeoJSON.

    Returns
    -------
    Path
        The written path.
    """
    features = []
    for tree in result.final_trees:
        if tree.status in {"removed", "dead"}:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [tree.lon, tree.lat]},
                "properties": {
                    "tree_id": tree.tree_id,
                    "species": tree.species,
                    "common_name": tree.common_name,
                    "dbh_cm": tree.dbh_cm,
                    "height_m": tree.height_m,
                    "crown_width_m": tree.crown_width_m,
                    "status": tree.status,
                    "native": tree.native,
                    "source": tree.source,
                },
            }
        )
    payload = {"type": "FeatureCollection", "features": features}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_dumps(payload), encoding="utf-8")
    return path


def metric_delta(before: CanopyMetrics, after: CanopyMetrics) -> dict[str, float]:
    """Calculate a concise set of metric deltas.

    Parameters
    ----------
    before : CanopyMetrics
        Baseline.
    after : CanopyMetrics
        Outcome.

    Returns
    -------
    dict of str to float
        Delta values.
    """
    return {
        "tree_count": float(after.tree_count - before.tree_count),
        "canopy_cover_pct": round(after.canopy_cover_pct - before.canopy_cover_pct, 3),
        "canopy_volume_m3": round(after.canopy_volume_m3 - before.canopy_volume_m3, 3),
        "total_carbon_kg": round(after.total_carbon_kg - before.total_carbon_kg, 3),
        "shannon_index": round(after.shannon_index - before.shannon_index, 4),
        "native_fraction": round(after.native_fraction - before.native_fraction, 4),
    }


def _boundary_polygon(dataset: UrbanForestDataset, crs: str) -> Polygon | None:
    """Project the dataset boundary into the terrain CRS.

    Parameters
    ----------
    dataset : UrbanForestDataset
        Dataset with a WGS84 boundary.
    crs : str
        Target CRS.

    Returns
    -------
    shapely.Polygon or None
        Boundary polygon, or ``None`` when the dataset has no boundary.
    """
    if not dataset.boundary:
        return None
    points = [project_lonlat(lon, lat, crs) for lon, lat in dataset.boundary]
    if len(points) < 3:
        return None
    polygon = Polygon(points)
    return polygon if polygon.is_valid else polygon.buffer(0)


def _building_polygon(
    rings: tuple[tuple[tuple[float, float], ...], ...],
    crs: str,
) -> Polygon:
    """Project a building footprint into the terrain CRS.

    Parameters
    ----------
    rings : tuple of tuple of tuple of float
        WGS84 rings.
    crs : str
        Target CRS.

    Returns
    -------
    shapely.Polygon
        Buffered polygon, always valid.
    """
    ring = rings[0] if rings else ()
    points = [project_lonlat(lon, lat, crs) for lon, lat in ring]
    polygon = Polygon(points) if len(points) >= 3 else Polygon()
    return polygon if polygon.is_valid else polygon.buffer(0)


def _nearest_distance(points: np.ndarray, x: float, y: float) -> float:
    """Return the distance from a point to the nearest point in an array.

    Parameters
    ----------
    points : numpy.ndarray
        Array of ``(x, y)`` pairs.
    x : float
        Query easting.
    y : float
        Query northing.

    Returns
    -------
    float
        Distance in metres, or a large number when the array is empty.
    """
    if points.size == 0:
        return 1_000.0
    distances = np.hypot(points[:, 0] - x, points[:, 1] - y)
    return float(np.min(distances))


def _grid_sample_xy(grid: TerrainGrid, x: float, y: float) -> tuple[float, float, float]:
    """Sample a terrain grid at a projected coordinate.

    Parameters
    ----------
    grid : TerrainGrid
        Terrain grid.
    x : float
        Easting.
    y : float
        Northing.

    Returns
    -------
    tuple of float
        Elevation, canopy height, and slope.
    """
    left, bottom, right, top = grid.bounds
    col = min(max(int((x - left) / max(right - left, 1e-9) * grid.width), 0), grid.width - 1)
    row = min(max(int((top - y) / max(top - bottom, 1e-9) * grid.height), 0), grid.height - 1)
    elevation = float(grid.elevation[row, col])
    canopy = float(grid.canopy_height[row, col]) if grid.canopy_height is not None else 0.0
    slope = float(
        np.hypot(
            np.gradient(grid.elevation, axis=1)[row, col] / max((right - left) / grid.width, 1e-9),
            np.gradient(grid.elevation, axis=0)[row, col] / max((top - bottom) / grid.height, 1e-9),
        )
        * 100.0
    )
    return (elevation, canopy, slope)


def _unproject(x: float, y: float, crs: str) -> tuple[float, float]:
    """Convert a projected coordinate to WGS84.

    Parameters
    ----------
    x : float
        Easting.
    y : float
        Northing.
    crs : str
        Source CRS.

    Returns
    -------
    tuple of float
        Longitude and latitude.
    """
    from pyproj import Transformer

    transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    lon, lat = transformer.transform(x, y)
    return (float(lon), float(lat))


def _json_dumps(payload: object) -> str:
    """Serialise a payload as compact JSON with a trailing newline.

    Parameters
    ----------
    payload : object
        JSON-safe payload.

    Returns
    -------
    str
        JSON text.
    """
    import json

    return json.dumps(payload, separators=(",", ":")) + "\n"
