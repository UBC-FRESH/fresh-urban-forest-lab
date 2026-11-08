#!/usr/bin/env python3
"""Build a citywide 2018→2022 LiDAR canopy-change product.

The script processes the 181 City of Vancouver 2018 LiDAR ZIPs one at a time,
builds a 5 m ground/canopy surface, aligns it with the P30 2022 CHM, and writes
a repeat-measures change product. It is a screening comparison, not tree
survival, growth, species change, ownership, or causal attribution.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from collections.abc import Sequence
from pathlib import Path

import laspy
import numpy as np
import rasterio
from numpy.typing import NDArray
from scipy.ndimage import distance_transform_edt

from fresh_urban_forest.change_product import build_change_product
from fresh_urban_forest.models import TerrainGrid

CITY_BOUNDS = (483_645.0, 5_449_578.0, 498_315.0, 5_460_349.0)
GROUND_CLASS = 2
CANOPY_CLASSES = (3, 5)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Parameters
    ----------
    argv : sequence of str or None
        Arguments.

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
    )
    parser.add_argument(
        "--later-root",
        type=Path,
        default=Path("data/processed/vancouver_2022"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/processed/change_vancouver_2018_2022_citywide"),
    )
    parser.add_argument("--resolution", type=float, default=5.0)
    parser.add_argument("--stride", type=int, default=32)
    parser.add_argument("--ground-source", choices=("lidar", "dem"), default="lidar")
    parser.add_argument("--vertical-offset", type=float, default=0.0)
    parser.add_argument("--threshold", type=float, default=2.0)
    return parser.parse_args(argv)


def grid_shape(
    bounds: tuple[float, float, float, float],
    resolution: float,
) -> tuple[int, int]:
    """Return the grid shape for bounds and resolution.

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
        When bounds or resolution are invalid.
    """
    left, bottom, right, top = bounds
    if right <= left or top <= bottom or resolution <= 0.0:
        raise ValueError("bounds and resolution must be positive")
    return (
        max(1, round((top - bottom) / resolution)),
        max(1, round((right - left) / resolution)),
    )


def tile_surfaces(
    zip_paths: Sequence[Path],
    *,
    bounds: tuple[float, float, float, float],
    shape: tuple[int, int],
    stride: int,
) -> tuple[NDArray[np.float32], NDArray[np.float32], NDArray[np.bool_], dict[str, int]]:
    """Build 2018 ground/canopy surfaces from all ZIP tiles.

    Parameters
    ----------
    zip_paths : sequence of Path
        ZIP files containing LAS.
    bounds : tuple of float
        Target bounds.
    shape : tuple of int
        Target shape.
    stride : int
        Point stride used for tractability.

    Returns
    -------
    tuple
        Ground elevation, canopy height, ground-valid mask, and counters.

    Raises
    ------
    ValueError
        When no ground points are found or stride is not positive.
    """
    if stride < 1:
        raise ValueError("stride must be positive")
    left, bottom, right, top = bounds
    height, width = shape
    ground = np.full(shape, np.inf, dtype=np.float64)
    canopy = np.full(shape, -np.inf, dtype=np.float64)
    counters = {"tiles": 0, "points": 0, "sampled": 0, "ground": 0, "canopy": 0}
    with tempfile.TemporaryDirectory(prefix="p43_las_") as temporary:
        temp_dir = Path(temporary)
        for index, zip_path in enumerate(zip_paths, start=1):
            with zipfile.ZipFile(zip_path) as archive:
                members = [name for name in archive.namelist() if name.lower().endswith(".las")]
                if not members:
                    continue
                archive.extract(members[0], temp_dir)
                las_path = temp_dir / members[0]
            try:
                with laspy.open(las_path) as source:
                    for points in source.chunk_iterator(5_000_000):
                        x = np.asarray(points.x, dtype=np.float64)[::stride]
                        y = np.asarray(points.y, dtype=np.float64)[::stride]
                        z = np.asarray(points.z, dtype=np.float64)[::stride]
                        classes = np.asarray(points.classification)[::stride]
                        counters["points"] += len(np.asarray(points.x))
                        counters["sampled"] += len(x)
                        columns = np.floor((x - left) / (right - left) * width).astype(np.int64)
                        rows = np.floor((top - y) / (top - bottom) * height).astype(np.int64)
                        inside = (columns >= 0) & (columns < width) & (rows >= 0) & (rows < height)
                        ground_mask = inside & (classes == GROUND_CLASS)
                        canopy_mask = inside & np.isin(classes, CANOPY_CLASSES)
                        if np.any(ground_mask):
                            np.minimum.at(
                                ground,
                                (rows[ground_mask], columns[ground_mask]),
                                z[ground_mask],
                            )
                            counters["ground"] += int(ground_mask.sum())
                        if np.any(canopy_mask):
                            np.maximum.at(
                                canopy,
                                (rows[canopy_mask], columns[canopy_mask]),
                                z[canopy_mask],
                            )
                            counters["canopy"] += int(canopy_mask.sum())
            finally:
                las_path.unlink(missing_ok=True)
            counters["tiles"] += 1
            if index % 10 == 0 or index == len(zip_paths):
                print(
                    f"tiles {index}/{len(zip_paths)} sampled={counters['sampled']}",
                    flush=True,
                )
    valid = np.isfinite(ground)
    if not np.any(valid):
        raise ValueError("no ground points were found")
    indices = distance_transform_edt(~valid, return_distances=False, return_indices=True)
    filled = ground[tuple(indices)]
    canopy_height = np.where(np.isfinite(canopy), canopy - filled, 0.0)
    canopy_height = np.maximum(canopy_height, 0.0)
    return (
        np.asarray(filled, dtype=np.float32),
        np.asarray(canopy_height, dtype=np.float32),
        np.asarray(valid, dtype=np.bool_),
        counters,
    )


def tile_canopy(
    zip_paths: Sequence[Path],
    *,
    bounds: tuple[float, float, float, float],
    shape: tuple[int, int],
    stride: int,
) -> tuple[NDArray[np.float32], dict[str, int]]:
    """Build a 2018 canopy-elevation surface from ZIP tiles.

    Parameters
    ----------
    zip_paths : sequence of Path
        ZIP files containing LAS.
    bounds : tuple of float
        Target bounds.
    shape : tuple of int
        Target shape.
    stride : int
        Point stride.

    Returns
    -------
    tuple
        Maximum canopy elevation and counters.

    Raises
    ------
    ValueError
        When stride is not positive.
    """
    if stride < 1:
        raise ValueError("stride must be positive")
    left, bottom, right, top = bounds
    height, width = shape
    canopy = np.full(shape, -np.inf, dtype=np.float64)
    counters = {"tiles": 0, "points": 0, "sampled": 0, "canopy": 0}
    with tempfile.TemporaryDirectory(prefix="p43_canopy_") as temporary:
        temp_dir = Path(temporary)
        for index, zip_path in enumerate(zip_paths, start=1):
            with zipfile.ZipFile(zip_path) as archive:
                members = [name for name in archive.namelist() if name.lower().endswith(".las")]
                if not members:
                    continue
                archive.extract(members[0], temp_dir)
                las_path = temp_dir / members[0]
            try:
                with laspy.open(las_path) as source:
                    for points in source.chunk_iterator(5_000_000):
                        x = np.asarray(points.x, dtype=np.float64)[::stride]
                        y = np.asarray(points.y, dtype=np.float64)[::stride]
                        z = np.asarray(points.z, dtype=np.float64)[::stride]
                        classes = np.asarray(points.classification)[::stride]
                        counters["points"] += len(np.asarray(points.x))
                        counters["sampled"] += len(x)
                        columns = np.floor((x - left) / (right - left) * width).astype(np.int64)
                        rows = np.floor((top - y) / (top - bottom) * height).astype(np.int64)
                        inside = (columns >= 0) & (columns < width) & (rows >= 0) & (rows < height)
                        canopy_mask = inside & np.isin(classes, CANOPY_CLASSES)
                        if np.any(canopy_mask):
                            np.maximum.at(
                                canopy,
                                (rows[canopy_mask], columns[canopy_mask]),
                                z[canopy_mask],
                            )
                            counters["canopy"] += int(canopy_mask.sum())
            finally:
                las_path.unlink(missing_ok=True)
            counters["tiles"] += 1
            if index % 10 == 0 or index == len(zip_paths):
                print(f"tiles {index}/{len(zip_paths)} sampled={counters['sampled']}", flush=True)
    return np.asarray(canopy, dtype=np.float32), counters


def read_mask(path: Path, shape: tuple[int, int]) -> NDArray[np.bool_]:
    """Read a mask at the target shape, treating nodata as false.

    Parameters
    ----------
    path : Path
        Mask raster.
    shape : tuple of int
        Target shape.

    Returns
    -------
    numpy.ndarray
        Boolean mask.
    """
    from rasterio.enums import Resampling

    with rasterio.open(path) as dataset:
        array = dataset.read(1, out_shape=shape, resampling=Resampling.nearest)
        nodata = dataset.nodata
    mask = array > 0
    if nodata is not None:
        mask &= array != nodata
    return np.asarray(mask, dtype=np.bool_)


def read_later(
    path: Path,
    bounds: tuple[float, float, float, float],
    shape: tuple[int, int],
) -> NDArray[np.float32]:
    """Read a P30 raster at the citywide target grid.

    Parameters
    ----------
    path : Path
        P30 raster.
    bounds : tuple of float
        Target bounds.
    shape : tuple of int
        Target shape.

    Returns
    -------
    numpy.ndarray
        Raster values.
    """
    with rasterio.open(path) as dataset:
        array = dataset.read(1, out_shape=shape, boundless=True, fill_value=np.nan)
    return np.asarray(array, dtype=np.float32)


def build_change(
    *,
    las_dir: Path,
    later_root: Path,
    out_dir: Path,
    bounds: tuple[float, float, float, float] = CITY_BOUNDS,
    resolution: float = 5.0,
    stride: int = 32,
    threshold_m: float = 2.0,
    ground_source: str = "lidar",
    vertical_offset: float = 0.0,
) -> Path:
    """Build the citywide change product.

    Parameters
    ----------
    las_dir : Path
        Directory of 2018 ZIP tiles.
    later_root : Path
        P30 2022 dataset directory.
    out_dir : Path
        Output directory.
    bounds : tuple of float
        Target bounds.
    resolution : float
        Grid resolution in metres.
    stride : int
        Point stride.
    threshold_m : float
        Canopy threshold.
    ground_source : str
        ``lidar`` for 2018 ground points or ``dem`` for the P30 2022 DEM.
    vertical_offset : float
        Offset added to the 2022 DEM when it stands in for 2018 ground.

    Returns
    -------
    Path
        Written ``change.json``.

    Raises
    ------
    FileNotFoundError
        When no ZIP tiles are present.
    """
    zip_paths = sorted(las_dir.glob("*.zip"))
    if not zip_paths:
        raise FileNotFoundError(las_dir)
    shape = grid_shape(bounds, resolution)
    later_elevation = read_later(later_root / "dem.tif", bounds, shape)
    if ground_source == "lidar":
        ground, earlier, valid, counters = tile_surfaces(
            zip_paths,
            bounds=bounds,
            shape=shape,
            stride=stride,
        )
        later = read_later(later_root / "chm.tif", bounds, shape)
        validity = valid & np.isfinite(later)
        earlier = np.where(validity, earlier, np.nan)
        later = np.where(validity, later, np.nan)
    else:
        aoi = read_mask(later_root / "aoi_mask.tif", shape)
        water = read_mask(later_root / "water_mask.tif", shape)
        building = read_mask(later_root / "building_mask.tif", shape)
        canopy_elevation, counters = tile_canopy(
            zip_paths,
            bounds=bounds,
            shape=shape,
            stride=stride,
        )
        ground = later_elevation + vertical_offset
        earlier = np.where(np.isfinite(canopy_elevation), canopy_elevation - ground, 0.0)
        earlier = np.maximum(earlier, 0.0)
        later = read_later(later_root / "chm.tif", bounds, shape)
        later = np.where(np.isfinite(later), later, 0.0)
        validity = aoi & ~water & ~building & np.isfinite(ground)
        earlier = np.where(validity, earlier, np.nan)
        later = np.where(validity, later, np.nan)
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
    path = build_change_product(
        earlier_grid,
        later_grid,
        out_dir,
        threshold_m=threshold_m,
        earlier_label="City of Vancouver LiDAR 2018 (citywide)",
        later_label="City of Vancouver LiDAR 2022 (citywide)",
    )
    sidecar = out_dir / "change_process.json"
    sidecar.write_text(
        json.dumps(
            {"counters": counters, "stride": stride, "resolution": resolution},
            indent=2,
        )
        + "\n"
    )
    return path


def main(argv: Sequence[str] | None = None) -> int:
    """Run the citywide change build.

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
        stride=args.stride,
        threshold_m=args.threshold,
        ground_source=args.ground_source,
        vertical_offset=args.vertical_offset,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    print(json.dumps({"change_json": str(path), "metrics": payload["metrics"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
