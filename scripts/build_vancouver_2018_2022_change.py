#!/usr/bin/env python3
"""Build a staged City of Vancouver 2018→2022 canopy-change product.

This script processes the two 2018 downtown LAS tiles and the P30 2022 CHM on a
common 1 m EPSG:3157 grid. It is a repeat-measures screening product, not a
growth rate, survival estimate, or ownership layer.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

import laspy
import numpy as np
import rasterio
from numpy.typing import NDArray
from rasterio.windows import from_bounds
from scipy.ndimage import distance_transform_edt

from fresh_urban_forest.change_product import build_change_product
from fresh_urban_forest.models import TerrainGrid

DEFAULT_BOUNDS = (492_000.0, 5_456_000.0, 494_000.0, 5_457_000.0)
GROUND_CLASS = 2
CANOPY_CLASSES = (3, 5)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Parameters
    ----------
    argv : sequence of str or None
        Arguments. ``None`` uses ``sys.argv``.

    Returns
    -------
    argparse.Namespace
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--las-dir",
        type=Path,
        default=Path("data/raw/city_lidar/2018/vancouver-lidar-2018"),
        help="Directory with 2018 LAS tiles",
    )
    parser.add_argument(
        "--later-root",
        type=Path,
        default=Path("data/processed/vancouver_2022"),
        help="P30 2022 dataset directory",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/processed/change_vancouver_2018_2022_downtown"),
    )
    parser.add_argument("--resolution", type=float, default=1.0)
    parser.add_argument("--threshold", type=float, default=2.0)
    return parser.parse_args(argv)


def grid_indices(
    x: NDArray[np.floating],
    y: NDArray[np.floating],
    *,
    bounds: tuple[float, float, float, float],
    shape: tuple[int, int],
) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    """Map projected coordinates to row and column indices.

    Parameters
    ----------
    x : numpy.ndarray
        Easting values.
    y : numpy.ndarray
        Northing values.
    bounds : tuple of float
        ``(left, bottom, right, top)``.
    shape : tuple of int
        ``(height, width)``.

    Returns
    -------
    tuple of numpy.ndarray
        Row and column indices. Points outside the grid get clipped indices.
    """
    left, bottom, right, top = bounds
    height, width = shape
    columns = np.floor((x - left) / (right - left) * width).astype(np.int64)
    rows = np.floor((top - y) / (top - bottom) * height).astype(np.int64)
    return np.clip(rows, 0, height - 1), np.clip(columns, 0, width - 1)


def las_surfaces(
    paths: Sequence[Path],
    *,
    bounds: tuple[float, float, float, float],
    shape: tuple[int, int],
) -> tuple[NDArray[np.float32], NDArray[np.float32], NDArray[np.bool_]]:
    """Build 2018 ground and canopy surfaces from LAS tiles.

    Parameters
    ----------
    paths : sequence of Path
        LAS files covering the bounds.
    bounds : tuple of float
        Target bounds.
    shape : tuple of int
        Target shape.

    Returns
    -------
    tuple of numpy.ndarray
        Ground elevation, canopy elevation, and ground-valid mask.

    Raises
    ------
    ValueError
        When no ground points are found.
    """
    ground = np.full(shape, np.inf, dtype=np.float64)
    canopy = np.full(shape, -np.inf, dtype=np.float64)
    for path in paths:
        with laspy.open(path) as source:
            for points in source.chunk_iterator(5_000_000):
                x = np.asarray(points.x, dtype=np.float64)
                y = np.asarray(points.y, dtype=np.float64)
                z = np.asarray(points.z, dtype=np.float64)
                classes = np.asarray(points.classification)
                rows, cols = grid_indices(x, y, bounds=bounds, shape=shape)
                ground_mask = classes == GROUND_CLASS
                canopy_mask = np.isin(classes, CANOPY_CLASSES)
                if np.any(ground_mask):
                    np.minimum.at(ground, (rows[ground_mask], cols[ground_mask]), z[ground_mask])
                if np.any(canopy_mask):
                    np.maximum.at(
                        canopy,
                        (rows[canopy_mask], cols[canopy_mask]),
                        z[canopy_mask],
                    )
    valid = np.isfinite(ground)
    if not np.any(valid):
        raise ValueError("no ground points were found in the supplied LAS tiles")
    indices = distance_transform_edt(~valid, return_distances=False, return_indices=True)
    filled = ground[tuple(indices)]
    canopy_height = np.where(np.isfinite(canopy), canopy - filled, 0.0)
    canopy_height = np.maximum(canopy_height, 0.0)
    return (
        np.asarray(filled, dtype=np.float32),
        np.asarray(canopy_height, dtype=np.float32),
        np.asarray(valid, dtype=np.bool_),
    )


def raster_window(
    path: Path,
    *,
    bounds: tuple[float, float, float, float],
    shape: tuple[int, int],
) -> NDArray[np.float32]:
    """Read a raster window aligned to the target grid.

    Parameters
    ----------
    path : Path
        GeoTIFF path.
    bounds : tuple of float
        Target bounds.
    shape : tuple of int
        Target shape.

    Returns
    -------
    numpy.ndarray
        Raster values at the target shape.
    """
    with rasterio.open(path) as dataset:
        window = from_bounds(*bounds, transform=dataset.transform)
        array = dataset.read(
            1,
            window=window,
            out_shape=shape,
            boundless=True,
            fill_value=np.nan,
        )
    return np.asarray(array, dtype=np.float32)


def build_change(
    *,
    las_dir: Path,
    later_root: Path,
    out_dir: Path,
    bounds: tuple[float, float, float, float] = DEFAULT_BOUNDS,
    resolution: float = 1.0,
    threshold_m: float = 2.0,
) -> Path:
    """Build the downtown 2018→2022 change product.

    Parameters
    ----------
    las_dir : Path
        Directory with the two 2018 LAS tiles.
    later_root : Path
        P30 2022 dataset directory.
    out_dir : Path
        Output directory.
    bounds : tuple of float
        Target bounds.
    resolution : float
        Grid resolution in metres.
    threshold_m : float
        Canopy threshold in metres.

    Returns
    -------
    Path
        Path to ``change.json``.

    Raises
    ------
    FileNotFoundError
        When no LAS tiles are present.
    """
    paths = sorted(las_dir.glob("*.las"))
    if not paths:
        raise FileNotFoundError(las_dir)
    left, bottom, right, top = bounds
    shape = (
        max(1, round((top - bottom) / resolution)),
        max(1, round((right - left) / resolution)),
    )
    ground, earlier, valid = las_surfaces(paths, bounds=bounds, shape=shape)
    later = raster_window(later_root / "chm.tif", bounds=bounds, shape=shape)
    later_elevation = raster_window(later_root / "dem.tif", bounds=bounds, shape=shape)
    later = np.where(np.isfinite(later), later, np.nan)
    validity = valid & np.isfinite(later)
    earlier = np.where(validity, earlier, np.nan)
    earlier_grid = TerrainGrid(
        crs="EPSG:3157",
        bounds=bounds,
        width=shape[1],
        height=shape[0],
        elevation=np.asarray(ground, dtype=np.float32),
        canopy_height=np.asarray(earlier, dtype=np.float32),
    )
    later_grid = TerrainGrid(
        crs="EPSG:3157",
        bounds=bounds,
        width=shape[1],
        height=shape[0],
        elevation=np.asarray(later_elevation, dtype=np.float32),
        canopy_height=np.asarray(later, dtype=np.float32),
    )
    return build_change_product(
        earlier_grid,
        later_grid,
        out_dir,
        threshold_m=threshold_m,
        earlier_label="City of Vancouver LiDAR 2018 (downtown pilot)",
        later_label="City of Vancouver LiDAR 2022 (downtown pilot)",
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the downtown change build.

    Parameters
    ----------
    argv : sequence of str or None
        Arguments.

    Returns
    -------
    int
        Zero on success.
    """
    args = parse_args(argv)
    path = build_change(
        las_dir=args.las_dir,
        later_root=args.later_root,
        out_dir=args.out,
        resolution=args.resolution,
        threshold_m=args.threshold,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    print(json.dumps({"change_json": str(path), "metrics": payload["metrics"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
