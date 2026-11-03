"""Raster shadow casting for buildings, tree crowns, and terrain.

The kernel is a transparent 2.5-D approximation. It projects building footprints and
ellipsoidal tree crowns onto a horizontal target plane along the solar vector, and
optionally adds a coarse terrain-horizon mask. It does not model penumbra, leaf
transmissivity, or facade geometry beyond a sampled target height.
"""

from __future__ import annotations

import datetime as dt
import io
import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageDraw
from scipy.ndimage import map_coordinates
from shapely.geometry import Polygon

from fresh_urban_forest.models import Building, TerrainGrid, TreeRecord, UrbanForestDataset
from fresh_urban_forest.solar import SolarPosition, solar_position
from fresh_urban_forest.terrain import project_lonlat

ShadowMode = Literal["combined", "building", "tree", "terrain"]


@dataclass(frozen=True, slots=True)
class ShadowMasks:
    """Boolean shadow masks on a dataset terrain grid.

    Attributes
    ----------
    crs : str
        Projected CRS.
    bounds : tuple of float
        ``(left, bottom, right, top)``.
    width : int
        Grid columns.
    height : int
        Grid rows.
    building : numpy.ndarray
        Building-cast shadow.
    tree : numpy.ndarray
        Tree-cast shadow.
    terrain : numpy.ndarray
        Terrain-horizon shadow.
    combined : numpy.ndarray
        Union of the three masks.
    target_height_m : float
        Height above ground of the target plane.
    solar : SolarPosition
        Solar position used for the cast.
    tree_count : int
        Trees that contributed a crown.
    building_count : int
        Buildings that contributed a footprint.
    terrain_included : bool
        Whether the terrain horizon was evaluated.
    """

    crs: str
    bounds: tuple[float, float, float, float]
    width: int
    height: int
    building: NDArray[np.bool_]
    tree: NDArray[np.bool_]
    terrain: NDArray[np.bool_]
    combined: NDArray[np.bool_]
    target_height_m: float
    solar: SolarPosition
    tree_count: int
    building_count: int
    terrain_included: bool

    @property
    def cell_area_m2(self) -> float:
        """Return the area of one grid cell in square metres.

        Returns
        -------
        float
            Cell area.
        """
        return (
            (self.bounds[2] - self.bounds[0])
            * (self.bounds[3] - self.bounds[1])
            / max(self.width * self.height, 1)
        )

    def to_dict(self) -> dict[str, object]:
        """Convert the non-array metadata to a JSON-safe dictionary.

        Returns
        -------
        dict
            Bounds, size, solar position, counts, and target height.
        """
        return {
            "crs": self.crs,
            "bounds": list(self.bounds),
            "width": self.width,
            "height": self.height,
            "target_height_m": self.target_height_m,
            "solar": self.solar.to_dict(),
            "tree_count": self.tree_count,
            "building_count": self.building_count,
            "terrain_included": self.terrain_included,
        }


def cast_shadows(
    dataset: UrbanForestDataset,
    when: dt.datetime,
    *,
    target_height_m: float = 1.5,
    include_terrain: bool = True,
    exclude_tree_id: str | None = None,
) -> ShadowMasks:
    """Cast building, tree, and optional terrain shadows for one instant.

    Parameters
    ----------
    dataset : UrbanForestDataset
        Dataset with terrain, buildings, and trees.
    when : datetime.datetime
        Evaluation instant.
    target_height_m : float
        Height above ground of the target plane, commonly 1.5 m for a pedestrian.
    include_terrain : bool
        Add a coarse terrain-horizon mask for grids of at most 40,000 cells.
    exclude_tree_id : str or None
        Skip one tree, used to compute marginal shade.

    Returns
    -------
    ShadowMasks
        Boolean masks and metadata.
    """
    grid = dataset.terrain
    position = solar_position(when, _center_lon(grid), _center_lat(grid))
    shape = (grid.height, grid.width)
    building = np.zeros(shape, dtype=np.bool_)
    tree = np.zeros(shape, dtype=np.bool_)
    terrain = np.zeros(shape, dtype=np.bool_)
    if position.altitude_deg > 0.5:
        building, building_count = _building_mask(
            dataset.buildings, grid, position, target_height_m
        )
        tree, tree_count = _tree_mask(
            dataset.trees, grid, position, target_height_m, exclude_tree_id
        )
        if include_terrain and grid.width * grid.height <= 40_000:
            terrain = _terrain_mask(grid, position, target_height_m)
        else:
            terrain = np.zeros(shape, dtype=np.bool_)
    else:
        building_count = 0
        tree_count = 0
    return ShadowMasks(
        crs=grid.crs,
        bounds=grid.bounds,
        width=grid.width,
        height=grid.height,
        building=building,
        tree=tree,
        terrain=terrain,
        combined=building | tree | terrain,
        target_height_m=target_height_m,
        solar=position,
        tree_count=tree_count,
        building_count=building_count,
        terrain_included=bool(np.any(terrain)),
    )


def shadow_mask_png(masks: ShadowMasks, *, mode: ShadowMode = "combined") -> bytes:
    """Render a shadow mask as a transparent PNG.

    Parameters
    ----------
    masks : ShadowMasks
        Masks to render.
    mode : str
        One of ``combined``, ``building``, ``tree``, or ``terrain``.

    Returns
    -------
    bytes
        PNG bytes.

    Raises
    ------
    ValueError
        When the mode is unknown.
    """
    if mode == "building":
        visible = masks.building
        rgba = _mask_rgba(visible, (43, 94, 170, 145))
    elif mode == "tree":
        visible = masks.tree
        rgba = _mask_rgba(visible, (45, 125, 72, 145))
    elif mode == "terrain":
        visible = masks.terrain
        rgba = _mask_rgba(visible, (90, 90, 90, 95))
    elif mode == "combined":
        rgba = np.zeros((masks.height, masks.width, 4), dtype=np.uint8)
        building_only = masks.building & ~masks.tree & ~masks.terrain
        tree_only = masks.tree & ~masks.building & ~masks.terrain
        overlap = (
            (masks.building & masks.tree)
            | (masks.building & masks.terrain)
            | (masks.tree & masks.terrain)
        )
        terrain_only = masks.terrain & ~masks.building & ~masks.tree
        rgba[building_only] = (43, 94, 170, 145)
        rgba[tree_only] = (45, 125, 72, 150)
        rgba[overlap] = (24, 54, 68, 175)
        rgba[terrain_only] = (90, 90, 90, 95)
    else:
        raise ValueError(f"unknown shadow mode: {mode}")
    image = Image.fromarray(rgba, mode="RGBA")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _building_mask(
    buildings: tuple[Building, ...],
    grid: TerrainGrid,
    solar: SolarPosition,
    target_height_m: float,
) -> tuple[NDArray[np.bool_], int]:
    """Rasterise building-cast shadows.

    Parameters
    ----------
    buildings : tuple of Building
        Buildings to project.
    grid : TerrainGrid
        Target grid.
    solar : SolarPosition
        Sun position.
    target_height_m : float
        Target plane height.

    Returns
    -------
    tuple of numpy.ndarray and int
        Boolean mask and contributing building count.
    """
    image = Image.new("L", (grid.width, grid.height), 0)
    draw = ImageDraw.Draw(image)
    direction = _shadow_direction(solar.azimuth_deg)
    count = 0
    for building in buildings:
        if not building.rings:
            continue
        ring = building.rings[0]
        points = [project_lonlat(lon, lat, grid.crs) for lon, lat in ring]
        if len(points) < 3:
            continue
        height = max(float(building.height_m), 0.0)
        if height <= target_height_m:
            continue
        offset = (height - target_height_m) / math.tan(math.radians(solar.altitude_deg))
        shifted = [(x + direction[0] * offset, y + direction[1] * offset) for x, y in points]
        hull = _convex_hull(points + shifted)
        if len(hull) < 3:
            continue
        draw.polygon([_project_to_pixel(x, y, grid) for x, y in hull], fill=1)
        count += 1
    return (np.asarray(image, dtype=np.uint8) > 0, count)


def _tree_mask(
    trees: tuple[TreeRecord, ...],
    grid: TerrainGrid,
    solar: SolarPosition,
    target_height_m: float,
    exclude_tree_id: str | None,
) -> tuple[NDArray[np.bool_], int]:
    """Rasterise tree-crown shadows as projected ellipses.

    Parameters
    ----------
    trees : tuple of TreeRecord
        Trees to project.
    grid : TerrainGrid
        Target grid.
    solar : SolarPosition
        Sun position.
    target_height_m : float
        Target plane height.
    exclude_tree_id : str or None
        Tree to skip.

    Returns
    -------
    tuple of numpy.ndarray and int
        Boolean mask and contributing tree count.
    """
    image = Image.new("L", (grid.width, grid.height), 0)
    draw = ImageDraw.Draw(image)
    direction = _shadow_direction(solar.azimuth_deg)
    perpendicular = (-direction[1], direction[0])
    count = 0
    altitude = max(math.radians(solar.altitude_deg), math.radians(1.0))
    for tree in trees:
        if tree.tree_id == exclude_tree_id or tree.status in {"removed", "dead"}:
            continue
        if tree.x_m is None or tree.y_m is None:
            continue
        height = max(float(tree.height_m or 0.0), 0.5)
        crown_width = max(float(tree.crown_width_m or 0.0), 0.5)
        crown_depth = max(height * min(max(float(tree.crown_ratio), 0.1), 0.95), 0.5)
        ground = float(tree.elevation_m if tree.elevation_m is not None else 0.0)
        crown_center = ground + height - crown_depth / 2.0
        if crown_center <= target_height_m:
            continue
        offset = (crown_center - target_height_m) / math.tan(altitude)
        center_x = tree.x_m + direction[0] * offset
        center_y = tree.y_m + direction[1] * offset
        minor = crown_width / 2.0
        major = min(minor / max(math.sin(altitude), 0.2), 250.0)
        points: list[tuple[float, float]] = []
        for step in range(20):
            angle = 2.0 * math.pi * step / 20.0
            along = major * math.cos(angle)
            across = minor * math.sin(angle)
            points.append(
                (
                    center_x + direction[0] * along + perpendicular[0] * across,
                    center_y + direction[1] * along + perpendicular[1] * across,
                )
            )
        draw.polygon([_project_to_pixel(x, y, grid) for x, y in points], fill=1)
        count += 1
    return (np.asarray(image, dtype=np.uint8) > 0, count)


def _terrain_mask(
    grid: TerrainGrid,
    solar: SolarPosition,
    target_height_m: float,
) -> NDArray[np.bool_]:
    """Estimate terrain-horizon shading with a coarse eight-direction horizon.

    Parameters
    ----------
    grid : TerrainGrid
        Terrain grid.
    solar : SolarPosition
        Sun position.
    target_height_m : float
        Target height above the ground.

    Returns
    -------
    numpy.ndarray
        Boolean terrain-shadow mask.
    """
    elevation = np.nan_to_num(np.asarray(grid.elevation, dtype=np.float64), nan=0.0)
    rows, cols = np.indices(elevation.shape, dtype=np.float64)
    cell_x = max((grid.bounds[2] - grid.bounds[0]) / max(grid.width, 1), 1e-6)
    cell_y = max((grid.bounds[3] - grid.bounds[1]) / max(grid.height, 1), 1e-6)
    max_distance = 300.0
    steps = 24
    horizon = np.full((8, grid.height, grid.width), -np.inf, dtype=np.float64)
    for index, azimuth in enumerate(range(0, 360, 45)):
        radians = math.radians(float(azimuth))
        dx = math.sin(radians)
        dy = math.cos(radians)
        for step in range(1, steps + 1):
            distance = max_distance * step / steps
            sample_rows = rows - dy * distance / cell_y
            sample_cols = cols + dx * distance / cell_x
            sampled = map_coordinates(
                elevation,
                [sample_rows, sample_cols],
                order=1,
                mode="nearest",
            )
            slope = (sampled - (elevation + target_height_m)) / distance
            horizon[index] = np.maximum(horizon[index], slope)
    index = round((solar.azimuth_deg % 360.0) / 45.0) % 8
    return np.asarray(
        horizon[index] > math.tan(math.radians(max(solar.altitude_deg, 1.0))),
        dtype=np.bool_,
    )


def _convex_hull(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Return a convex hull of projected points.

    Parameters
    ----------
    points : list of tuple of float
        Input points.

    Returns
    -------
    list of tuple of float
        Hull exterior points, or an empty list when the geometry is invalid.
    """
    try:
        hull = Polygon(points).convex_hull
    except Exception:
        return []
    if hull.is_empty or not hasattr(hull, "exterior"):
        return []
    return [(float(x), float(y)) for x, y in list(hull.exterior.coords)[:-1]]


def _shadow_direction(azimuth_deg: float) -> tuple[float, float]:
    """Return the horizontal unit vector from the sun toward the shadow.

    Parameters
    ----------
    azimuth_deg : float
        Solar azimuth clockwise from north.

    Returns
    -------
    tuple of float
        ``(east, north)`` unit vector.
    """
    radians = math.radians(azimuth_deg)
    return (-math.sin(radians), -math.cos(radians))


def _project_to_pixel(x: float, y: float, grid: TerrainGrid) -> tuple[float, float]:
    """Project a CRS coordinate to a raster pixel coordinate.

    Parameters
    ----------
    x : float
        Easting.
    y : float
        Northing.
    grid : TerrainGrid
        Target grid.

    Returns
    -------
    tuple of float
        ``(column, row)`` in pixel space.
    """
    left, bottom, right, top = grid.bounds
    col = (x - left) / max(right - left, 1e-9) * grid.width
    row = (top - y) / max(top - bottom, 1e-9) * grid.height
    return (col, row)


def _mask_rgba(mask: NDArray[np.bool_], colour: tuple[int, int, int, int]) -> NDArray[np.uint8]:
    """Render one mask as an RGBA array.

    Parameters
    ----------
    mask : numpy.ndarray
        Boolean mask.
    colour : tuple of int
        RGBA colour.

    Returns
    -------
    numpy.ndarray
        RGBA array.
    """
    rgba = np.zeros((*mask.shape, 4), dtype=np.uint8)
    rgba[mask] = colour
    return rgba


def _center_lon(grid: TerrainGrid) -> float:
    """Return the centre longitude of a grid.

    Parameters
    ----------
    grid : TerrainGrid
        Terrain grid.

    Returns
    -------
    float
        Longitude.
    """
    from fresh_urban_forest.terrain import unproject_xy

    left, bottom, right, top = grid.bounds
    return unproject_xy((left + right) / 2.0, (bottom + top) / 2.0, grid.crs)[0]


def _center_lat(grid: TerrainGrid) -> float:
    """Return the centre latitude of a grid.

    Parameters
    ----------
    grid : TerrainGrid
        Terrain grid.

    Returns
    -------
    float
        Latitude.
    """
    from fresh_urban_forest.terrain import unproject_xy

    left, bottom, right, top = grid.bounds
    return unproject_xy((left + right) / 2.0, (bottom + top) / 2.0, grid.crs)[1]
