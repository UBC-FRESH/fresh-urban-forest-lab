#!/usr/bin/env python3
"""Build a Vancouver canopy-gap and above-ground opportunity screen.

The product uses public City of Vancouver LiDAR surfaces, public OSM road
centrelines, and the P38 shade-equity cells. It does not model utilities,
ownership, access, soil, irrigation, or field conditions.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from numpy.typing import NDArray
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.transform import from_origin

from fresh_urban_forest.planting_opportunity import (
    GAP_EVIDENCE,
    OPPORTUNITY_EVIDENCE,
    build_gap_masks,
    build_opportunity_grid,
    write_opportunity_product,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Parameters
    ----------
    argv : list of str or None
        Arguments. ``None`` uses ``sys.argv``.

    Returns
    -------
    argparse.Namespace
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("data/processed/vancouver_2022"),
        help="City dataset directory with DEM, CHM, masks, and roads",
    )
    parser.add_argument(
        "--heat-priority",
        type=Path,
        default=Path("data/processed/vancouver_2022/heat_priority.json"),
        help="P38 heat-priority JSON",
    )
    parser.add_argument("--out", type=Path, default=None, help="Output directory")
    parser.add_argument("--resolution", type=float, default=5.0, help="Raster cell size")
    parser.add_argument("--cell-size", type=float, default=400.0, help="Analysis cell size")
    parser.add_argument("--slope-max", type=float, default=15.0, help="Maximum slope degrees")
    parser.add_argument("--gap-distance", type=float, default=15.0, help="Canopy gap distance")
    parser.add_argument("--street-distance", type=float, default=10.0, help="Street adjacency")
    return parser.parse_args(argv)


def raster_shape(
    bounds: tuple[float, float, float, float],
    resolution: float,
) -> tuple[int, int]:
    """Return the raster shape for a bounds and resolution.

    Parameters
    ----------
    bounds : tuple of float
        ``(left, bottom, right, top)``.
    resolution : float
        Cell size in metres.

    Returns
    -------
    tuple of int
        ``(height, width)``.

    Raises
    ------
    ValueError
        When the bounds or resolution are invalid.
    """
    left, bottom, right, top = bounds
    if right <= left or top <= bottom or resolution <= 0.0:
        raise ValueError("bounds and resolution must be positive")
    return (
        max(1, math.ceil((top - bottom) / resolution)),
        max(1, math.ceil((right - left) / resolution)),
    )


def _read(path: Path, shape: tuple[int, int], *, resampling: Resampling) -> NDArray[np.float32]:
    """Read one raster band at a target shape."""
    with rasterio.open(path) as dataset:
        array = dataset.read(1, out_shape=shape, resampling=resampling)
    return np.asarray(array, dtype=np.float32)


def _read_mask(path: Path, shape: tuple[int, int]) -> NDArray[np.bool_]:
    """Read a numeric mask, treating nodata as false."""
    with rasterio.open(path) as dataset:
        array = dataset.read(1, out_shape=shape, resampling=Resampling.nearest)
        nodata = dataset.nodata
    mask = array > 0
    if nodata is not None:
        mask &= array != nodata
    return np.asarray(mask, dtype=np.bool_)


def load_rasters(
    root: Path,
    resolution: float,
) -> tuple[
    NDArray[np.float32],
    NDArray[np.float32],
    NDArray[np.bool_],
    NDArray[np.bool_],
    tuple[float, float, float, float],
    str,
]:
    """Load DEM, canopy, building mask, water mask, bounds, and CRS.

    Parameters
    ----------
    root : Path
        City dataset directory.
    resolution : float
        Target cell size in metres.

    Returns
    -------
    tuple
        DEM, canopy height, building mask, water mask, bounds, and CRS.

    Raises
    ------
    FileNotFoundError
        When terrain metadata is missing.
    """
    terrain_path = root / "terrain.json"
    if not terrain_path.exists():
        raise FileNotFoundError(terrain_path)
    terrain = json.loads(terrain_path.read_text(encoding="utf-8"))
    bounds = tuple(float(value) for value in terrain["bounds"])
    shape = raster_shape((bounds[0], bounds[1], bounds[2], bounds[3]), resolution)
    dem = _read(root / "dem.tif", shape, resampling=Resampling.average)
    canopy = _read(root / "chm.tif", shape, resampling=Resampling.average)
    building = _read_mask(root / "building_mask.tif", shape)
    water = _read_mask(root / "water_mask.tif", shape)
    return (
        np.nan_to_num(dem, nan=0.0),
        np.nan_to_num(canopy, nan=0.0),
        building,
        water,
        (bounds[0], bounds[1], bounds[2], bounds[3]),
        str(terrain["crs"]),
    )


def load_roads(
    path: Path,
    crs: str,
) -> gpd.GeoDataFrame:
    """Load the public road centrelines from a compressed GeoJSON file.

    Parameters
    ----------
    path : Path
        Gzipped GeoJSON road file.
    crs : str
        Target projected CRS.

    Returns
    -------
    geopandas.GeoDataFrame
        Road centrelines in the target CRS.

    Raises
    ------
    FileNotFoundError
        When the road file is missing.
    """
    if not path.exists():
        raise FileNotFoundError(path)
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    roads = gpd.GeoDataFrame.from_features(payload.get("features", []), crs="EPSG:4326")
    return roads.to_crs(crs)


def road_masks(
    roads: gpd.GeoDataFrame,
    *,
    bounds: tuple[float, float, float, float],
    shape: tuple[int, int],
    surface_buffer_m: float = 3.0,
) -> tuple[NDArray[np.bool_], NDArray[np.bool_]]:
    """Rasterise road-surface and road-centreline masks.

    Parameters
    ----------
    roads : geopandas.GeoDataFrame
        Road centrelines in the raster CRS.
    bounds : tuple of float
        ``(left, bottom, right, top)``.
    shape : tuple of int
        ``(height, width)``.
    surface_buffer_m : float
        Road-surface buffer in metres.

    Returns
    -------
    tuple of numpy.ndarray
        Surface mask and centreline mask.
    """
    height, width = shape
    left, bottom, right, top = bounds
    transform = from_origin(left, top, (right - left) / width, (top - bottom) / height)
    geometries = [geometry for geometry in roads.geometry if geometry is not None]
    surface = rasterize(
        ((geometry.buffer(surface_buffer_m), 1) for geometry in geometries),
        out_shape=shape,
        transform=transform,
        fill=0,
        dtype="uint8",
    )
    centre = rasterize(
        ((geometry, 1) for geometry in geometries),
        out_shape=shape,
        transform=transform,
        fill=0,
        dtype="uint8",
        all_touched=True,
    )
    return (
        np.asarray(surface > 0, dtype=np.bool_),
        np.asarray(centre > 0, dtype=np.bool_),
    )


def load_priority(path: Path) -> dict[str, dict[str, object]]:
    """Load P38 cells keyed by cell id.

    Parameters
    ----------
    path : Path
        P38 heat-priority JSON.

    Returns
    -------
    dict
        Cell id to properties.

    Raises
    ------
    FileNotFoundError
        When the heat-priority file is missing.
    """
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(cell.get("cell_id")): dict(cell) for cell in payload.get("cells", [])}


def build_product(
    *,
    root: Path,
    heat_priority: Path,
    out_dir: Path,
    resolution: float = 5.0,
    cell_size: float = 400.0,
    slope_max: float = 15.0,
    gap_distance: float = 15.0,
    street_distance: float = 10.0,
) -> dict[str, object]:
    """Build and write the planting-opportunity product.

    Parameters
    ----------
    root : Path
        City dataset directory.
    heat_priority : Path
        P38 heat-priority JSON.
    out_dir : Path
        Output directory.
    resolution : float
        Raster cell size in metres.
    cell_size : float
        Analysis cell size in metres.
    slope_max : float
        Maximum slope in degrees.
    gap_distance : float
        Canopy-gap distance in metres.
    street_distance : float
        Street-adjacency distance in metres.

    Returns
    -------
    dict
        Product summary and written paths.
    """
    dem, canopy, building, water, bounds, crs = load_rasters(root, resolution)
    roads = load_roads(root / "roads.geojson.gz", crs)
    surface, centre = road_masks(roads, bounds=bounds, shape=dem.shape)
    masks = build_gap_masks(
        dem=dem,
        canopy_height=canopy,
        building_mask=building,
        water_mask=water,
        road_surface_mask=surface,
        road_center_mask=centre,
        cell_size_m=resolution,
        gap_distance_m=gap_distance,
        street_distance_m=street_distance,
        slope_max_deg=slope_max,
    )
    priority = load_priority(heat_priority)
    cells = tuple(
        cell
        for cell in build_opportunity_grid(
            masks,
            bounds=bounds,
            crs=crs,
            priority=priority,
            cell_size_m=cell_size,
        )
        if cell.cell_id in priority
    )
    metadata: dict[str, object] = {
        "dataset_id": "vancouver-city-2022",
        "cell_size_m": cell_size,
        "raster_resolution_m": resolution,
        "bounds": list(bounds),
        "crs": crs,
        "gap": masks.to_dict(),
        "methods": {
            "gap": GAP_EVIDENCE.to_dict(),
            "opportunity": OPPORTUNITY_EVIDENCE.to_dict(),
        },
        "crown_area_assumptions_m2": {
            "small": 13.2,
            "medium": 45.4,
            "large": 183.9,
        },
        "caveats": [
            "This is an above-ground screening layer, not a planting plan.",
            "Underground and overhead utilities are not available; they are not modelled.",
            "Ownership, access, soil volume, irrigation, maintenance, and cost are not modelled.",
            "Capacity values are gross upper bounds from gap area divided by crown area; "
            "they are not tree counts.",
            "Road surfaces are excluded, but adjacent boulevards are not confirmed public "
            "planting space.",
        ],
    }
    paths = write_opportunity_product(
        cells,
        out_dir,
        crs=crs,
        metadata=metadata,
        stem="planting_opportunity",
    )
    meta_path = out_dir / "planting_opportunity_meta.json"
    meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return {
        "cell_count": len(cells),
        "gap_summary": masks.summary,
        "high_tier_cells": sum(1 for cell in cells if cell.opportunity_tier == "high"),
        "paths": {name: str(path) for name, path in paths.items()} | {"metadata": str(meta_path)},
    }


def main(argv: list[str] | None = None) -> int:
    """Run the Vancouver opportunity build.

    Parameters
    ----------
    argv : list of str or None
        Command-line arguments.

    Returns
    -------
    int
        Zero on success.
    """
    args = parse_args(argv)
    out_dir = args.out or args.root
    result = build_product(
        root=args.root,
        heat_priority=args.heat_priority,
        out_dir=out_dir,
        resolution=args.resolution,
        cell_size=args.cell_size,
        slope_max=args.slope_max,
        gap_distance=args.gap_distance,
        street_distance=args.street_distance,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
