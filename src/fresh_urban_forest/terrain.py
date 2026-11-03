"""Raster terrain, canopy-height sampling, and canopy metrics.

The module keeps every calculation in the projected CRS of the source rasters. Trees are
transformed from WGS84 only at the edge, so metric areas and volumes stay in metres.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import rasterio
from numpy.typing import NDArray
from pyproj import Transformer

from fresh_urban_forest.models import TerrainGrid

WGS84 = "EPSG:4326"


@dataclass(frozen=True, slots=True)
class RasterData:
    """A single-band raster held in memory.

    Attributes
    ----------
    path : Path
        Source path.
    crs : str
        CRS string.
    transform : object
        Affine transform from rasterio.
    bounds : tuple of float
        ``(left, bottom, right, top)``.
    array : numpy.ndarray
        Two-dimensional array with ``numpy.nan`` for nodata cells.
    cell_area_m2 : float
        Area of one cell in square metres.
    """

    path: Path
    crs: str
    transform: object
    bounds: tuple[float, float, float, float]
    array: NDArray[np.float32]
    cell_area_m2: float

    @property
    def shape(self) -> tuple[int, int]:
        """Return the raster shape as ``(rows, columns)``.

        Returns
        -------
        tuple of int
            Array shape.
        """
        return (int(self.array.shape[0]), int(self.array.shape[1]))


def read_raster(path: Path, *, band: int = 1) -> RasterData:
    """Read a single band from a raster and mask its nodata value.

    Parameters
    ----------
    path : Path
        Raster path.
    band : int
        One-based band index.

    Returns
    -------
    RasterData
        The in-memory raster.

    Raises
    ------
    ValueError
        When the raster has no CRS.
    """
    with rasterio.open(path) as dataset:
        if dataset.crs is None:
            raise ValueError(f"raster has no CRS: {path}")
        array = dataset.read(band).astype(np.float32)
        if dataset.nodata is not None:
            array = np.where(array == np.float32(dataset.nodata), np.nan, array)
        array = np.where(np.isfinite(array), array, np.nan)
        transform = dataset.transform
        cell_area = abs(float(transform.a) * float(transform.e))
        return RasterData(
            path=path,
            crs=str(dataset.crs),
            transform=transform,
            bounds=(
                float(dataset.bounds.left),
                float(dataset.bounds.bottom),
                float(dataset.bounds.right),
                float(dataset.bounds.top),
            ),
            array=array,
            cell_area_m2=cell_area,
        )


@lru_cache(maxsize=16)
def transformer_to(crs: str) -> Transformer:
    """Build a WGS84-to-target transformer.

    Parameters
    ----------
    crs : str
        Target CRS.

    Returns
    -------
    pyproj.Transformer
        Transformer with ``always_xy`` enabled.
    """
    return Transformer.from_crs(WGS84, crs, always_xy=True)


@lru_cache(maxsize=16)
def _transformer_from(crs: str) -> Transformer:
    """Build and cache a target-CRS-to-WGS84 transformer.

    Parameters
    ----------
    crs : str
        Source CRS.

    Returns
    -------
    pyproj.Transformer
        Transformer with ``always_xy`` enabled.
    """
    return Transformer.from_crs(crs, WGS84, always_xy=True)


def project_lonlat(lon: float, lat: float, crs: str) -> tuple[float, float]:
    """Project one WGS84 coordinate into a target CRS.

    Parameters
    ----------
    lon : float
        Longitude.
    lat : float
        Latitude.
    crs : str
        Target CRS.

    Returns
    -------
    tuple of float
        ``(x, y)`` in the target CRS.
    """
    x, y = transformer_to(crs).transform(lon, lat)
    return (float(x), float(y))


def unproject_xy(x: float, y: float, crs: str) -> tuple[float, float]:
    """Convert a projected coordinate back to WGS84.

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
        ``(lon, lat)`` in WGS84.
    """
    lon, lat = _transformer_from(crs).transform(x, y)
    return (float(lon), float(lat))


def sample_raster(
    raster: RasterData, xs: NDArray[np.float64], ys: NDArray[np.float64]
) -> NDArray[np.float64]:
    """Sample a raster at projected coordinates with nearest-neighbour lookup.

    Parameters
    ----------
    raster : RasterData
        Raster to sample.
    xs : numpy.ndarray
        Easting values.
    ys : numpy.ndarray
        Northing values.

    Returns
    -------
    numpy.ndarray
        Sampled values, with ``numpy.nan`` outside the raster.
    """
    rows, cols = rasterio.transform.rowcol(raster.transform, xs, ys)
    row_index = np.asarray(rows, dtype=np.int64)
    col_index = np.asarray(cols, dtype=np.int64)
    output = np.full(xs.shape, np.nan, dtype=np.float64)
    valid = (
        (row_index >= 0)
        & (row_index < raster.array.shape[0])
        & (col_index >= 0)
        & (col_index < raster.array.shape[1])
    )
    if np.any(valid):
        output[valid] = raster.array[row_index[valid], col_index[valid]].astype(np.float64)
    return output


def sample_raster_lonlat(
    raster: RasterData,
    lon: NDArray[np.float64],
    lat: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Sample a raster at WGS84 coordinates.

    Parameters
    ----------
    raster : RasterData
        Raster to sample.
    lon : numpy.ndarray
        Longitudes.
    lat : numpy.ndarray
        Latitudes.

    Returns
    -------
    numpy.ndarray
        Sampled values.
    """
    transformer = transformer_to(raster.crs)
    xs, ys = transformer.transform(lon, lat)
    return sample_raster(raster, np.asarray(xs), np.asarray(ys))


def build_terrain_grid(
    dem: RasterData,
    chm: RasterData | None = None,
    *,
    max_size: int = 180,
) -> TerrainGrid:
    """Downsample a DEM and an optional CHM into a compact render grid.

    Parameters
    ----------
    dem : RasterData
        Bare-earth elevation.
    chm : RasterData or None
        Canopy height. When provided it must share the DEM grid.
    max_size : int
        Maximum number of rows or columns in the output.

    Returns
    -------
    TerrainGrid
        A regular grid in the DEM CRS.

    Notes
    -----
    When the DEM and CHM differ by a row or column at the edge, both are trimmed to
    their common upper-left window. The DEM transform and bounds define the output grid.
    """
    source_elevation = np.asarray(dem.array)
    source_canopy = np.asarray(chm.array) if chm is not None else None
    if source_canopy is not None and source_canopy.shape != source_elevation.shape:
        rows = min(source_elevation.shape[0], source_canopy.shape[0])
        cols = min(source_elevation.shape[1], source_canopy.shape[1])
        source_elevation = source_elevation[:rows, :cols]
        source_canopy = source_canopy[:rows, :cols]
    step = max(1, math.ceil(max(source_elevation.shape) / max_size))
    elevation = _block_reduce(source_elevation, step)
    canopy = _block_reduce(source_canopy, step) if source_canopy is not None else None
    left, bottom, right, top = dem.bounds
    return TerrainGrid(
        crs=dem.crs,
        bounds=(left, bottom, right, top),
        width=int(elevation.shape[1]),
        height=int(elevation.shape[0]),
        elevation=elevation.astype(np.float32),
        canopy_height=canopy.astype(np.float32) if canopy is not None else None,
    )


def canopy_cover_pct(
    chm: NDArray[np.float32] | NDArray[np.float64],
    *,
    threshold_m: float = 2.0,
    cell_area_m2: float = 1.0,
) -> float:
    """Calculate canopy cover from a canopy-height grid.

    Parameters
    ----------
    chm : numpy.ndarray
        Canopy height in metres.
    threshold_m : float
        Minimum height counted as canopy.
    cell_area_m2 : float
        Area represented by one cell.

    Returns
    -------
    float
        Canopy cover in percent. Nodata cells are excluded from the denominator.
    """
    array = np.asarray(chm, dtype=np.float64)
    valid = np.isfinite(array)
    if not np.any(valid):
        return 0.0
    covered = np.count_nonzero(array[valid] >= threshold_m)
    return 100.0 * covered / float(np.count_nonzero(valid))


def canopy_volume_m3(
    chm: NDArray[np.float32] | NDArray[np.float64],
    *,
    cell_area_m2: float = 1.0,
) -> float:
    """Calculate a raster canopy-volume estimate.

    Parameters
    ----------
    chm : numpy.ndarray
        Canopy height in metres.
    cell_area_m2 : float
        Area represented by one cell.

    Returns
    -------
    float
        Sum of positive canopy heights times cell area, in cubic metres. This is a
        height-field prism, not a lidar-derived crown hull.
    """
    array = np.asarray(chm, dtype=np.float64)
    values = np.where(np.isfinite(array), np.maximum(array, 0.0), 0.0)
    return float(values.sum() * cell_area_m2)


def height_percentiles(
    chm: NDArray[np.float32] | NDArray[np.float64],
    *,
    percentiles: tuple[float, ...] = (50.0, 75.0, 95.0),
) -> dict[str, float]:
    """Summarise canopy-height percentiles over valid cells.

    Parameters
    ----------
    chm : numpy.ndarray
        Canopy height in metres.
    percentiles : tuple of float
        Percentiles to calculate.

    Returns
    -------
    dict of str to float
        Keys such as ``p50``, ``p95``, plus ``max`` and ``mean``.
    """
    array = np.asarray(chm, dtype=np.float64)
    valid = array[np.isfinite(array) & (array > 0.0)]
    if valid.size == 0:
        return {"mean": 0.0, "max": 0.0, **{f"p{int(p)}": 0.0 for p in percentiles}}
    result = {
        "mean": float(np.mean(valid)),
        "max": float(np.max(valid)),
    }
    for percentile in percentiles:
        result[f"p{int(percentile)}"] = float(np.percentile(valid, percentile))
    return result


def slope_percent(grid: TerrainGrid) -> NDArray[np.float32]:
    """Calculate slope from a terrain grid using Horn's 3 by 3 operator.

    Parameters
    ----------
    grid : TerrainGrid
        Terrain grid.

    Returns
    -------
    numpy.ndarray
        Slope in percent, shape matching the grid.
    """
    elevation = np.asarray(grid.elevation, dtype=np.float64)
    cell_x = (grid.bounds[2] - grid.bounds[0]) / max(grid.width, 1)
    cell_y = (grid.bounds[3] - grid.bounds[1]) / max(grid.height, 1)
    dzdx = np.gradient(elevation, axis=1) / max(cell_x, 1e-9)
    dzdy = np.gradient(elevation, axis=0) / max(cell_y, 1e-9)
    return (100.0 * np.hypot(dzdx, dzdy)).astype(np.float32)


def sample_terrain_grid(
    grid: TerrainGrid,
    lon: float,
    lat: float,
) -> tuple[float, float, float]:
    """Sample elevation and canopy height at a WGS84 coordinate.

    Parameters
    ----------
    grid : TerrainGrid
        Terrain grid.
    lon : float
        Longitude.
    lat : float
        Latitude.

    Returns
    -------
    tuple of float
        ``(elevation_m, canopy_height_m, slope_percent)``. Missing values are zero.
    """
    x, y = project_lonlat(lon, lat, grid.crs)
    left, bottom, right, top = grid.bounds
    col = int((x - left) / max(right - left, 1e-9) * grid.width)
    row = int((top - y) / max(top - bottom, 1e-9) * grid.height)
    col = min(max(col, 0), grid.width - 1)
    row = min(max(row, 0), grid.height - 1)
    elevation = float(grid.elevation[row, col])
    canopy = float(grid.canopy_height[row, col]) if grid.canopy_height is not None else 0.0
    slope = float(slope_percent(grid)[row, col])
    return (elevation, canopy, slope)


def grid_cell_center(grid: TerrainGrid, row: int, col: int) -> tuple[float, float]:
    """Return the projected centre of a grid cell.

    Parameters
    ----------
    grid : TerrainGrid
        Terrain grid.
    row : int
        Row index.
    col : int
        Column index.

    Returns
    -------
    tuple of float
        ``(x, y)`` in the grid CRS.
    """
    left, bottom, right, top = grid.bounds
    x = left + (col + 0.5) * (right - left) / max(grid.width, 1)
    y = top - (row + 0.5) * (top - bottom) / max(grid.height, 1)
    return (float(x), float(y))


def _block_reduce(array: NDArray[np.float32], step: int) -> NDArray[np.float32]:
    """Average non-overlapping blocks, preserving nodata as zero in the output.

    Parameters
    ----------
    array : numpy.ndarray
        Input array.
    step : int
        Block size in cells.

    Returns
    -------
    numpy.ndarray
        Reduced array.
    """
    if step <= 1:
        return np.nan_to_num(array, nan=0.0)
    rows = array.shape[0] // step
    cols = array.shape[1] // step
    trimmed = array[: rows * step, : cols * step]
    reshaped = trimmed.reshape(rows, step, cols, step)
    with np.errstate(invalid="ignore"):
        reduced = np.nanmean(reshaped, axis=(1, 3))
    return np.nan_to_num(reduced, nan=0.0).astype(np.float32)
