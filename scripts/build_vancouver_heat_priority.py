#!/usr/bin/env python3
"""Build a Vancouver shade and social-equity screening product.

The script uses public City of Vancouver LiDAR surfaces and public Statistics
Canada 2021 Census dissemination-area profiles. It does not use CanopyFit code
or the unavailable municipal constraint layers.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import geopandas as gpd
import numpy as np
import rasterio
from numpy.typing import NDArray
from rasterio.enums import Resampling

from fresh_urban_forest.census import (
    build_equity_frame,
    equity_summary,
    load_profiles,
)
from fresh_urban_forest.heat_priority import (
    PRIORITY_EVIDENCE,
    SHADE_EVIDENCE,
    build_priority_grid,
    raster_shade,
    write_priority_product,
)

ZONE = ZoneInfo("America/Vancouver")
DEFAULT_HOURS = (10, 12, 14, 16)


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
        help="City dataset directory with dem.tif and chm.tif",
    )
    parser.add_argument(
        "--census-dir",
        type=Path,
        default=Path("data/raw/census_2021"),
        help="Directory with Census Profile CSVs and da_geometry_vancouver.geojson",
    )
    parser.add_argument("--out", type=Path, default=None, help="Output directory")
    parser.add_argument("--resolution", type=float, default=5.0, help="Shade raster metres")
    parser.add_argument("--cell-size", type=float, default=400.0, help="Analysis cell metres")
    parser.add_argument("--year", type=int, default=2022, help="Solar sample year")
    return parser.parse_args(argv)


def time_samples(year: int) -> tuple[dt.datetime, ...]:
    """Return two representative summer days at four daylight hours.

    Parameters
    ----------
    year : int
        Calendar year used only for solar geometry.

    Returns
    -------
    tuple of datetime.datetime
        Eight local-time samples.
    """
    return tuple(
        dt.datetime(year, month, day, hour, tzinfo=ZONE)
        for month, day in ((7, 15), (8, 15))
        for hour in DEFAULT_HOURS
    )


def raster_shape(
    bounds: tuple[float, float, float, float],
    resolution: float,
) -> tuple[int, int]:
    """Return the raster shape for a bounds and cell size.

    Parameters
    ----------
    bounds : tuple of float
        ``(left, bottom, right, top)``.
    resolution : float
        Target cell size in metres.

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


def _read_resampled(
    path: Path,
    shape: tuple[int, int],
    *,
    resampling: Resampling = Resampling.average,
) -> NDArray[np.float32]:
    """Read one raster band at a target shape."""
    with rasterio.open(path) as dataset:
        array = dataset.read(1, out_shape=shape, resampling=resampling)
    return np.asarray(array, dtype=np.float32)


def _read_mask(path: Path, shape: tuple[int, int]) -> NDArray[np.bool_]:
    """Read a numeric mask at a target shape, treating nodata as false."""
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
    NDArray[np.float32],
    NDArray[np.bool_],
    NDArray[np.bool_],
    tuple[float, float, float, float],
    str,
]:
    """Load aligned ground, canopy, building, and mask rasters.

    Parameters
    ----------
    root : Path
        Dataset directory.
    resolution : float
        Target cell size in metres.

    Returns
    -------
    tuple
        DEM, canopy height, building height, building mask, water mask,
        bounds, and CRS.

    Raises
    ------
    FileNotFoundError
        When a required raster or terrain metadata file is missing.
    """
    terrain_path = root / "terrain.json"
    if not terrain_path.exists():
        raise FileNotFoundError(terrain_path)
    terrain = json.loads(terrain_path.read_text(encoding="utf-8"))
    bounds = tuple(float(value) for value in terrain["bounds"])
    shape = raster_shape((bounds[0], bounds[1], bounds[2], bounds[3]), resolution)
    dem = _read_resampled(root / "dem.tif", shape)
    canopy = _read_resampled(root / "chm.tif", shape)
    building = _read_resampled(root / "building_height.tif", shape)
    building_mask = _read_mask(root / "building_mask.tif", shape)
    water_mask = _read_mask(root / "water_mask.tif", shape)
    return (
        np.nan_to_num(dem, nan=0.0),
        np.nan_to_num(canopy, nan=0.0),
        np.nan_to_num(building, nan=0.0),
        building_mask,
        water_mask,
        (bounds[0], bounds[1], bounds[2], bounds[3]),
        str(terrain["crs"]),
    )


def load_census(census_dir: Path) -> tuple[gpd.GeoDataFrame, dict[str, object]]:
    """Load Census geometry and build the social-equity frame.

    Parameters
    ----------
    census_dir : Path
        Directory with the Census CSV exports and Vancouver DA geometry.

    Returns
    -------
    tuple of geopandas.GeoDataFrame and dict
        Equity frame and summary.

    Raises
    ------
    FileNotFoundError
        When the Vancouver DA geometry file is absent.
    """
    geometry_path = census_dir / "da_geometry_vancouver.geojson"
    if not geometry_path.exists():
        raise FileNotFoundError(geometry_path)
    geometry = gpd.read_file(geometry_path)
    profiles = load_profiles(census_dir)
    reference = geometry["DGUID"].astype(str).tolist()
    frame = build_equity_frame(geometry, profiles, reference=reference)
    return frame, equity_summary(frame)


def build_product(
    *,
    root: Path,
    census_dir: Path,
    out_dir: Path,
    resolution: float = 5.0,
    cell_size: float = 400.0,
    year: int = 2022,
) -> dict[str, object]:
    """Build and write the shade-equity product.

    Parameters
    ----------
    root : Path
        City dataset directory.
    census_dir : Path
        Census input directory.
    out_dir : Path
        Output directory.
    resolution : float
        Shade raster cell size in metres.
    cell_size : float
        Analysis cell size in metres.
    year : int
        Solar sample year.

    Returns
    -------
    dict
        Product metadata and written path strings.
    """
    dem, canopy, building, building_mask, water_mask, bounds, crs = load_rasters(root, resolution)
    equity, census_summary = load_census(census_dir)
    whens = time_samples(year)
    shade = raster_shade(
        dem=dem,
        canopy_height=canopy,
        building_height=building,
        bounds=bounds,
        crs=crs,
        whens=whens,
    )
    cells = tuple(
        cell
        for cell in build_priority_grid(
            shade,
            bounds=bounds,
            crs=crs,
            canopy_height=canopy,
            building_mask=building_mask,
            water_mask=water_mask,
            equity=equity,
            cell_size_m=cell_size,
        )
        if math.isfinite(cell.equity_score)
    )
    manifest_path = root / "manifest.json"
    dataset_id = "vancouver-city-2022"
    if manifest_path.exists():
        dataset_id = str(
            json.loads(manifest_path.read_text(encoding="utf-8")).get("dataset_id", dataset_id)
        )
    metadata: dict[str, object] = {
        "dataset_id": dataset_id,
        "cell_size_m": cell_size,
        "shade_resolution_m": resolution,
        "bounds": list(bounds),
        "crs": crs,
        "time_samples": [when.isoformat() for when in whens],
        "shade": shade.to_dict(),
        "census": census_summary,
        "methods": {
            "shade": SHADE_EVIDENCE.to_dict(),
            "priority": PRIORITY_EVIDENCE.to_dict(),
        },
        "caveats": [
            "This is a screening surface, not a planting permit or a private-tree census.",
            "Shade deficit is not plantable area; above-ground constraints are not modelled.",
            "The equity score is relative to Vancouver dissemination areas and uses four "
            "Census indicators; it does not include land-surface temperature.",
            "LiDAR canopy and building heights are opaque geometry; leaf transparency and "
            "penumbra are not modelled.",
        ],
    }
    paths = write_priority_product(
        cells,
        out_dir,
        crs=crs,
        metadata=metadata,
        stem="heat_priority",
    )
    meta_path = out_dir / "heat_priority_meta.json"
    meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return {
        "dataset_id": dataset_id,
        "cell_count": len(cells),
        "shade_metrics": shade.metrics,
        "census": census_summary,
        "paths": {name: str(path) for name, path in paths.items()} | {"metadata": str(meta_path)},
    }


def main(argv: list[str] | None = None) -> int:
    """Run the Vancouver shade-equity build.

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
        census_dir=args.census_dir,
        out_dir=out_dir,
        resolution=args.resolution,
        cell_size=args.cell_size,
        year=args.year,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
