"""Point-cloud ingestion and canopy-height derivation.

The prototype does not depend on PDAL. It reads LAZ/LAS with ``laspy`` and bins the
highest return in each DEM cell, which is enough to build a defensible first-pass CHM and
to show where a full LiDAR pipeline would plug in.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import laspy
import numpy as np
import rasterio
from numpy.typing import NDArray

from fresh_urban_forest.terrain import RasterData, read_raster

GROUND_CLASSES: frozenset[int] = frozenset({2, 9, 18})
EXCLUDED_CLASSES: frozenset[int] = frozenset({7, 9, 18})


@dataclass(frozen=True, slots=True)
class PointCloudSummary:
    """Summary statistics for one LAS or LAZ file.

    Attributes
    ----------
    path : str
        Source path.
    point_count : int
        Number of points.
    bounds : tuple of float
        ``(min_x, min_y, min_z, max_x, max_y, max_z)``.
    crs : str
        CRS reported by the file, or an empty string.
    class_counts : tuple of tuple of int and int
        Point counts by classification code.
    density_per_m2 : float
        Average point density over the tile footprint.
    height_mean_m : float
        Mean height above the minimum z.
    height_p95_m : float
        95th percentile height above the minimum z.
    """

    path: str
    point_count: int
    bounds: tuple[float, float, float, float, float, float]
    crs: str
    class_counts: tuple[tuple[int, int], ...]
    density_per_m2: float
    height_mean_m: float
    height_p95_m: float


def summarize_point_cloud(path: Path) -> PointCloudSummary:
    """Read a LAS or LAZ file and summarise its extent, classes, and heights.

    Parameters
    ----------
    path : Path
        LAS or LAZ path.

    Returns
    -------
    PointCloudSummary
        Summary statistics.
    """
    class_counts: dict[int, int] = {}
    total = 0
    minimum_z = math.inf
    maximum_z = -math.inf
    heights: list[NDArray[np.float64]] = []
    with laspy.open(path) as reader:
        header = reader.header
        bounds = (
            float(header.mins[0]),
            float(header.mins[1]),
            float(header.mins[2]),
            float(header.maxs[0]),
            float(header.maxs[1]),
            float(header.maxs[2]),
        )
        crs = str(header.parse_crs() or "")
        for points in reader.chunk_iterator(2_000_000):
            z = np.asarray(points.z, dtype=np.float64)
            total += int(points.__len__())
            minimum_z = min(minimum_z, float(np.nanmin(z)))
            maximum_z = max(maximum_z, float(np.nanmax(z)))
            heights.append(z[:: max(1, len(z) // 50_000)])
            classes, counts = np.unique(np.asarray(points.classification), return_counts=True)
            for code, count in zip(classes.tolist(), counts.tolist(), strict=True):
                class_counts[int(code)] = class_counts.get(int(code), 0) + int(count)
    height_values = np.concatenate(heights) if heights else np.asarray([0.0])
    height_values = height_values - minimum_z
    width = max(bounds[3] - bounds[0], 1.0)
    depth = max(bounds[4] - bounds[1], 1.0)
    return PointCloudSummary(
        path=str(path),
        point_count=total,
        bounds=bounds,
        crs=crs,
        class_counts=tuple(sorted(class_counts.items())),
        density_per_m2=round(total / (width * depth), 3),
        height_mean_m=round(float(np.mean(height_values)), 3),
        height_p95_m=round(float(np.percentile(height_values, 95)), 3),
    )


def build_chm_from_points(
    point_path: Path | Sequence[Path],
    dem: RasterData,
    *,
    resolution_m: float = 1.0,
    include_ground: bool = False,
    empty_value: float = 0.0,
    source_crs: str | None = None,
    exclude_classes: Sequence[int] | None = None,
) -> RasterData:
    """Build a canopy-height model by binning the highest return per DEM cell.

    Parameters
    ----------
    point_path : Path or sequence of Path
        One LAS/LAZ path, or several tiles that are binned into the same grid.
    dem : RasterData
        Bare-earth DEM that defines the output grid.
    resolution_m : float
        Requested cell size. The DEM grid is used as-is; this value is recorded for the
        caller and must be within ten percent of the DEM cell size.
    include_ground : bool
        When ``False``, ground-classified points are ignored.
    empty_value : float
        Value assigned to cells with no usable return. Use ``numpy.nan`` when the result
        will be compared with another date and empty cells must be excluded.
    source_crs : str or None
        CRS of the point coordinates when it differs from the DEM CRS. The coordinates are
        transformed to the DEM CRS before binning.
    exclude_classes : sequence of int or None
        Additional ASPRS classes to exclude, such as buildings (6) in a city product.

    Returns
    -------
    RasterData
        A canopy-height raster aligned with the DEM.

    Raises
    ------
    ValueError
        When ``resolution_m`` is incompatible with the DEM grid.
    """
    dem_resolution = math.sqrt(dem.cell_area_m2)
    if abs(resolution_m - dem_resolution) / max(dem_resolution, 1e-9) > 0.10:
        raise ValueError("requested resolution differs from the DEM grid by more than ten percent")
    paths: list[Path] = (
        [point_path] if isinstance(point_path, Path) else [Path(item) for item in point_path]
    )
    transformer = None
    if source_crs and source_crs != dem.crs:
        from pyproj import Transformer

        transformer = Transformer.from_crs(source_crs, dem.crs, always_xy=True)
    maximum = np.full(dem.array.shape, -np.inf, dtype=np.float64)
    transform = dem.transform
    for path in paths:
        with laspy.open(path) as reader:
            for points in reader.chunk_iterator(2_000_000):
                classes = np.asarray(points.classification)
                keep = (
                    np.ones(classes.shape, dtype=bool)
                    if include_ground
                    else ~np.isin(classes, list(GROUND_CLASSES))
                )
                excluded = set(EXCLUDED_CLASSES) | set(exclude_classes or ())
                keep &= ~np.isin(classes, list(excluded))
                if not np.any(keep):
                    continue
                x = np.asarray(points.x, dtype=np.float64)[keep]
                y = np.asarray(points.y, dtype=np.float64)[keep]
                z = np.asarray(points.z, dtype=np.float64)[keep]
                if transformer is not None:
                    x, y = transformer.transform(x, y)
                rows, cols = rasterio.transform.rowcol(transform, x, y)
                rows = np.asarray(rows, dtype=np.int64)
                cols = np.asarray(cols, dtype=np.int64)
                valid = (
                    (rows >= 0)
                    & (rows < maximum.shape[0])
                    & (cols >= 0)
                    & (cols < maximum.shape[1])
                )
                np.maximum.at(maximum, (rows[valid], cols[valid]), z[valid])
    canopy = np.where(np.isfinite(maximum), maximum - dem.array, empty_value)
    canopy = np.clip(canopy, 0.0, None)
    return RasterData(
        path=paths[0],
        crs=dem.crs,
        transform=dem.transform,
        bounds=dem.bounds,
        array=canopy.astype(np.float32),
        cell_area_m2=dem.cell_area_m2,
    )


def canopies_from_pair(dsm_path: Path, dem_path: Path) -> RasterData:
    """Derive a canopy-height model from a DSM and a DEM.

    Parameters
    ----------
    dsm_path : Path
        Digital surface model.
    dem_path : Path
        Digital elevation model on the same grid.

    Returns
    -------
    RasterData
        Canopy height, clamped at zero.

    Notes
    -----
    When the grids differ by a row or column at the edge, both are trimmed to their common
    upper-left window.
    """
    dsm = read_raster(dsm_path)
    dem = read_raster(dem_path)
    first = np.asarray(dsm.array)
    second = np.asarray(dem.array)
    if first.shape != second.shape:
        rows = min(first.shape[0], second.shape[0])
        cols = min(first.shape[1], second.shape[1])
        first = first[:rows, :cols]
        second = second[:rows, :cols]
    canopy = np.clip(np.nan_to_num(first - second, nan=0.0), 0.0, None)
    return RasterData(
        path=dsm_path,
        crs=dem.crs,
        transform=dem.transform,
        bounds=dem.bounds,
        array=canopy.astype(np.float32),
        cell_area_m2=dem.cell_area_m2,
    )
