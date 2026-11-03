"""Individual-tree detection from a canopy-height grid.

This is a compact, dependency-light reimplementation of the well-known
local-maxima plus marker-controlled watershed workflow used by ForestTools, lidR, and
PyCrown. It does not copy their code; it implements the published idea from scratch with
``scipy.ndimage`` so the project keeps one small, auditable algorithm instead of a hard
dependency on an R or Cython stack.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from fresh_urban_forest.models import TerrainGrid
from fresh_urban_forest.terrain import unproject_xy


@dataclass(frozen=True, slots=True)
class DetectedTree:
    """One tree detected from a canopy-height grid.

    Attributes
    ----------
    tree_id : str
        Generated identifier.
    row : int
        Grid row of the crown centroid.
    col : int
        Grid column of the crown centroid.
    height_m : float
        Maximum canopy height in the crown segment.
    crown_radius_m : float
        Equivalent crown radius from the segment area.
    crown_area_m2 : float
        Segment area in square metres.
    x : float
        Projected easting of the centroid.
    y : float
        Projected northing of the centroid.
    lon : float
        Longitude of the centroid.
    lat : float
        Latitude of the centroid.
    """

    tree_id: str
    row: int
    col: int
    height_m: float
    crown_radius_m: float
    crown_area_m2: float
    x: float
    y: float
    lon: float
    lat: float


def detect_trees(
    grid: TerrainGrid,
    *,
    min_height_m: float = 3.0,
    window_m: float = 3.0,
    max_trees: int = 100_000,
) -> tuple[DetectedTree, ...]:
    """Detect individual tree crowns with local maxima and watershed segmentation.

    Parameters
    ----------
    grid : TerrainGrid
        Terrain grid with a canopy-height array.
    min_height_m : float
        Minimum canopy height for a candidate tree top.
    window_m : float
        Moving-window diameter for local maxima, in metres.
    max_trees : int
        Safety limit on the number of detected crowns.

    Returns
    -------
    tuple of DetectedTree
        Detected crowns, highest first.

    Raises
    ------
    ValueError
        When the grid has no canopy-height array.
    """
    if grid.canopy_height is None:
        raise ValueError("grid has no canopy_height array")
    canopy = np.nan_to_num(np.asarray(grid.canopy_height, dtype=np.float64), nan=0.0)
    if float(np.max(canopy)) < min_height_m:
        return ()
    cell_x = (grid.bounds[2] - grid.bounds[0]) / max(grid.width, 1)
    cell_y = (grid.bounds[3] - grid.bounds[1]) / max(grid.height, 1)
    cell_size = max((cell_x + cell_y) / 2.0, 1e-9)
    window_px = max(3, round(window_m / cell_size))
    if window_px % 2 == 0:
        window_px += 1
    filtered = ndimage.maximum_filter(canopy, size=window_px, mode="nearest")
    maxima = (canopy == filtered) & (canopy >= min_height_m)
    labels, count = ndimage.label(maxima)
    if count == 0:
        return ()
    # Keep one seed per connected plateau.
    markers = labels.astype(np.int32)
    canopy_max = float(np.max(canopy))
    inverted = ((canopy_max - canopy) / max(canopy_max, 1e-9) * 65535.0).astype(np.uint16)
    try:
        segments = ndimage.watershed_ift(inverted, markers)
    except (RuntimeError, ValueError):
        segments = markers
    segment_labels = np.unique(segments)
    trees: list[DetectedTree] = []
    for label in segment_labels:
        if label <= 0:
            continue
        mask = segments == label
        area_cells = int(np.count_nonzero(mask))
        if area_cells == 0:
            continue
        rows, cols = np.nonzero(mask)
        peak = float(np.max(canopy[rows, cols]))
        if peak < min_height_m:
            continue
        row = round(float(rows.mean()))
        col = round(float(cols.mean()))
        area_m2 = area_cells * cell_x * cell_y
        x = grid.bounds[0] + (col + 0.5) * cell_x
        y = grid.bounds[3] - (row + 0.5) * cell_y
        lon, lat = unproject_xy(x, y, grid.crs)
        trees.append(
            DetectedTree(
                tree_id=f"detected-{len(trees) + 1}",
                row=row,
                col=col,
                height_m=round(peak, 2),
                crown_radius_m=round(float(np.sqrt(area_m2 / np.pi)), 2),
                crown_area_m2=round(area_m2, 2),
                x=round(float(x), 2),
                y=round(float(y), 2),
                lon=round(lon, 8),
                lat=round(lat, 8),
            )
        )
        if len(trees) >= max_trees:
            break
    trees.sort(key=lambda tree: -tree.height_m)
    return tuple(trees)


def detected_trees_geojson(trees: tuple[DetectedTree, ...]) -> dict[str, object]:
    """Convert detected trees to a GeoJSON FeatureCollection.

    Parameters
    ----------
    trees : tuple of DetectedTree
        Detected trees.

    Returns
    -------
    dict
        GeoJSON FeatureCollection.
    """
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [tree.lon, tree.lat]},
                "properties": {
                    "tree_id": tree.tree_id,
                    "height_m": tree.height_m,
                    "crown_radius_m": tree.crown_radius_m,
                    "crown_area_m2": tree.crown_area_m2,
                },
            }
            for tree in trees
        ],
    }
