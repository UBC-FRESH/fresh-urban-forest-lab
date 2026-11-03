"""Build the JSON payload shared by the 2D map and the 3D scene.

The payload carries one explicit local origin. Both renderers use it, so a tree selected
on the map and a tree selected in the Three.js scene refer to the same record and the same
metres. Longitudes and latitudes are kept for MapLibre; local metres are kept for WebGL.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

from fresh_urban_forest.allometry import species_group, tree_carbon_kg, tree_crown_volume_m3
from fresh_urban_forest.models import TerrainGrid, TreeRecord, UrbanForestDataset
from fresh_urban_forest.terrain import project_lonlat, unproject_xy


def build_scene(
    dataset: UrbanForestDataset,
    trees: Sequence[TreeRecord] | None = None,
    *,
    max_trees: int = 50_000,
) -> dict[str, object]:
    """Build a compact scene payload for the browser.

    Parameters
    ----------
    dataset : UrbanForestDataset
        Dataset that supplies terrain, buildings, and boundary.
    trees : sequence of TreeRecord or None
        Tree population to render. Defaults to the dataset population.
    max_trees : int
        Maximum number of trees in the payload. The highest trees are kept when the
        population is larger.

    Returns
    -------
    dict
        JSON-safe scene payload.
    """
    population = tuple(trees) if trees is not None else dataset.trees
    if len(population) > max_trees:
        population = tuple(sorted(population, key=lambda tree: -(tree.height_m or 0.0))[:max_trees])
    grid = dataset.terrain
    left, bottom, right, top = grid.bounds
    positioned = [
        (tree.x_m, tree.y_m) for tree in population if tree.x_m is not None and tree.y_m is not None
    ]
    if positioned:
        origin_x = float(np.mean([point[0] for point in positioned]))
        origin_y = float(np.mean([point[1] for point in positioned]))
    else:
        origin_x = (left + right) / 2.0
        origin_y = (bottom + top) / 2.0
    origin_z = float(np.nanmin(grid.elevation)) if grid.elevation.size else 0.0
    origin_lon, origin_lat = unproject_xy(origin_x, origin_y, grid.crs)
    corner_lons: list[float] = []
    corner_lats: list[float] = []
    for corner_x, corner_y in ((left, bottom), (right, bottom), (right, top), (left, top)):
        lon, lat = unproject_xy(corner_x, corner_y, grid.crs)
        corner_lons.append(lon)
        corner_lats.append(lat)
    tree_payload = [_tree_payload(tree, origin_x, origin_y, origin_z) for tree in population]
    building_payload = [
        {
            "id": building.building_id,
            "name": building.name,
            "height_m": building.height_m,
            "rings": [[list(point) for point in ring] for ring in building.rings],
            "rings_local": [
                [_local_point(lon, lat, origin_x, origin_y, grid.crs) for lon, lat in ring]
                for ring in building.rings
            ],
            "base_z": _building_base_z(building.rings, grid, origin_z),
        }
        for building in dataset.buildings
    ]
    return {
        "dataset_id": dataset.manifest.dataset_id,
        "name": dataset.manifest.name,
        "crs": grid.crs,
        "origin": {"x": origin_x, "y": origin_y, "z": origin_z},
        "origin_lonlat": [origin_lon, origin_lat],
        "meters_per_degree": [
            111_320.0 * math.cos(math.radians(origin_lat)),
            110_540.0,
        ],
        "bounds": list(grid.bounds),
        "bounds_wgs84": [
            min(corner_lons),
            min(corner_lats),
            max(corner_lons),
            max(corner_lats),
        ],
        "terrain": {
            "width": grid.width,
            "height": grid.height,
            "bounds": list(grid.bounds),
            "elevation": [round(float(value), 2) for value in grid.elevation.ravel()],
            "canopy_height": [
                round(float(value), 2)
                for value in (
                    grid.canopy_height.ravel()
                    if grid.canopy_height is not None
                    else np.zeros(grid.width * grid.height, dtype=np.float32)
                )
            ],
        },
        "trees": tree_payload,
        "buildings": building_payload,
        "boundary": [list(point) for point in dataset.boundary],
        "metrics": {
            "tree_count": dataset.manifest.metrics.tree_count,
            "canopy_cover_pct": dataset.manifest.metrics.canopy_cover_pct,
            "canopy_volume_m3": dataset.manifest.metrics.canopy_volume_m3,
            "total_carbon_kg": dataset.manifest.metrics.total_carbon_kg,
        },
    }


def _tree_payload(
    tree: TreeRecord, origin_x: float, origin_y: float, origin_z: float
) -> dict[str, object]:
    """Build one tree payload.

    Parameters
    ----------
    tree : TreeRecord
        Tree to convert.
    origin_x : float
        Local origin easting.
    origin_y : float
        Local origin northing.
    origin_z : float
        Local origin elevation.

    Returns
    -------
    dict
        JSON-safe tree.
    """
    x = tree.x_m if tree.x_m is not None else 0.0
    y = tree.y_m if tree.y_m is not None else 0.0
    z = tree.elevation_m if tree.elevation_m is not None else origin_z
    group = species_group(tree.species or tree.common_name)
    return {
        "id": tree.tree_id,
        "lon": tree.lon,
        "lat": tree.lat,
        "x": round(x - origin_x, 2),
        "y": round(y - origin_y, 2),
        "z": round(z - origin_z, 2),
        "height": round(float(tree.height_m or 0.0), 2),
        "crown_width": round(float(tree.crown_width_m or 0.0), 2),
        "dbh_cm": round(float(tree.dbh_cm or 0.0), 2),
        "crown_ratio": round(float(tree.crown_ratio), 3),
        "species": tree.species,
        "common_name": tree.common_name,
        "genus": tree.genus,
        "group": group,
        "native": bool(tree.native),
        "status": tree.status,
        "source": tree.source,
        "crown_volume_m3": round(tree_crown_volume_m3(tree), 3),
        "carbon_kg": round(tree_carbon_kg(tree), 3),
        "color": _color(group, bool(tree.native)),
    }


def _building_base_z(
    rings: tuple[tuple[tuple[float, float], ...], ...],
    grid: TerrainGrid,
    origin_z: float,
) -> float:
    """Estimate a building base elevation from the terrain grid.

    Parameters
    ----------
    rings : tuple of tuple of tuple of float
        Building rings in WGS84.
    grid : TerrainGrid
        Terrain grid that supplies the base elevation.
    origin_z : float
        Scene vertical origin.

    Returns
    -------
    float
        Base elevation relative to the scene origin, or zero when the ring is empty.
    """
    if not rings or not rings[0]:
        return 0.0
    lon = sum(point[0] for point in rings[0]) / len(rings[0])
    lat = sum(point[1] for point in rings[0]) / len(rings[0])
    x, y = project_lonlat(lon, lat, grid.crs)
    left, bottom, right, top = grid.bounds
    col = min(max(int((x - left) / max(right - left, 1e-9) * grid.width), 0), grid.width - 1)
    row = min(max(int((top - y) / max(top - bottom, 1e-9) * grid.height), 0), grid.height - 1)
    return round(float(grid.elevation[row, col]) - origin_z, 2)


def _local_point(lon: float, lat: float, origin_x: float, origin_y: float, crs: str) -> list[float]:
    """Convert a WGS84 point to local metres.

    Parameters
    ----------
    lon : float
        Longitude.
    lat : float
        Latitude.
    origin_x : float
        Local origin easting.
    origin_y : float
        Local origin northing.
    crs : str
        Projected CRS.

    Returns
    -------
    list of float
        ``[x, y]`` in local metres.
    """
    x, y = project_lonlat(lon, lat, crs)
    return [round(x - origin_x, 2), round(y - origin_y, 2)]


def _color(group: str, native: bool) -> str:
    """Choose a display colour from species group and nativity.

    Parameters
    ----------
    group : str
        Species group.
    native : bool
        Whether the tree is native.

    Returns
    -------
    str
        Hex colour.
    """
    if group == "conifer":
        return "#2f6b4f" if native else "#4f8a6a"
    if group == "deciduous":
        return "#8ebf5a" if native else "#b7c96a"
    return "#8d8d8d"


def scene_bounds_local(dataset: UrbanForestDataset) -> tuple[float, float, float, float]:
    """Return the local scene extent in metres.

    Parameters
    ----------
    dataset : UrbanForestDataset
        Dataset to measure.

    Returns
    -------
    tuple of float
        ``(min_x, min_y, max_x, max_y)`` relative to the scene origin.
    """
    left, bottom, right, top = dataset.terrain.bounds
    width = right - left
    depth = top - bottom
    return (-width / 2.0, -depth / 2.0, width / 2.0, depth / 2.0)


def distance_m(first: TreeRecord, second: TreeRecord) -> float:
    """Calculate the planar distance between two trees.

    Parameters
    ----------
    first : TreeRecord
        First tree.
    second : TreeRecord
        Second tree.

    Returns
    -------
    float
        Distance in metres, or ``math.inf`` when either coordinate is missing.
    """
    if first.x_m is None or first.y_m is None or second.x_m is None or second.y_m is None:
        return math.inf
    return math.hypot(first.x_m - second.x_m, first.y_m - second.y_m)
