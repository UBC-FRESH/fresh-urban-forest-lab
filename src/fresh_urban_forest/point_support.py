"""Per-crown vegetation point support for city-scale candidate refinement.

The module deliberately works on a 1 m vegetation-point count grid. It does not read
LAS files itself; the operator script fills that grid one tile at a time and this module
provides the deterministic tile and crown-sum operations.
"""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
from numpy.typing import NDArray

TILE_M = 1000
RESOLUTION_M = 1.0


def tile_id(x: float, y: float, *, tile_m: int = TILE_M) -> str:
    """Return the City 1 km tile identifier containing a projected point.

    Parameters
    ----------
    x : float
        Easting.
    y : float
        Northing.
    tile_m : int, optional
        Tile side in metres.

    Returns
    -------
    str
        Identifier such as ``491000_5457000``.
    """
    return f"{math.floor(x / tile_m) * tile_m}_{math.floor(y / tile_m) * tile_m}"


def tile_origin(tile: str) -> tuple[float, float]:
    """Return the lower-left projected origin of a tile identifier.

    Parameters
    ----------
    tile : str
        Tile identifier.

    Returns
    -------
    tuple of float
        Easting and northing of the tile origin.
    """
    left, bottom = tile.split("_")
    return (float(left), float(bottom))


@lru_cache(maxsize=32)
def _disk_offsets(radius_cells: int) -> tuple[tuple[int, int], ...]:
    offsets: list[tuple[int, int]] = []
    for row in range(-radius_cells, radius_cells + 1):
        for col in range(-radius_cells, radius_cells + 1):
            if row * row + col * col <= radius_cells * radius_cells:
                offsets.append((row, col))
    return tuple(offsets)


def crown_support(
    counts: NDArray[np.uint32],
    x: float,
    y: float,
    radius_m: float,
    *,
    left: float,
    bottom: float,
    resolution_m: float = RESOLUTION_M,
) -> tuple[int, float]:
    """Sum vegetation points in a candidate crown disk.

    Parameters
    ----------
    counts : numpy.ndarray
        Two-dimensional count grid for one 1 km tile.
    x : float
        Candidate easting.
    y : float
        Candidate northing.
    radius_m : float
        Candidate crown radius in metres.
    left : float
        Tile left edge.
    bottom : float
        Tile bottom edge.
    resolution_m : float, optional
        Grid resolution.

    Returns
    -------
    tuple of int and float
        Count inside the disk and count per crown square metre.
    """
    radius = max(float(radius_m), 1.0)
    radius_cells = max(1, math.ceil(radius / resolution_m))
    row = math.floor((y - bottom) / resolution_m)
    col = math.floor((x - left) / resolution_m)
    total = 0
    for row_offset, col_offset in _disk_offsets(radius_cells):
        candidate_row = row + row_offset
        candidate_col = col + col_offset
        if 0 <= candidate_row < counts.shape[0] and 0 <= candidate_col < counts.shape[1]:
            total += int(counts[candidate_row, candidate_col])
    area = math.pi * radius * radius
    return total, total / area if area else 0.0


def _as_float(value: object) -> float:
    if isinstance(value, (int, float, str)):
        return float(value)
    return 0.0


def support_rows(
    counts: NDArray[np.uint32],
    rows: list[dict[str, object]],
    *,
    left: float,
    bottom: float,
    resolution_m: float = RESOLUTION_M,
) -> list[dict[str, object]]:
    """Attach support counts to candidate rows for one tile.

    Parameters
    ----------
    counts : numpy.ndarray
        Two-dimensional count grid.
    rows : list of dict
        Candidate rows with ``candidate_id``, ``x_m``, ``y_m``, and
        ``crown_radius_m``.
    left : float
        Tile left edge.
    bottom : float
        Tile bottom edge.
    resolution_m : float, optional
        Grid resolution.

    Returns
    -------
    list of dict
        Rows with ``point_count`` and ``point_density``.
    """
    result: list[dict[str, object]] = []
    for row in rows:
        count, density = crown_support(
            counts,
            _as_float(row["x_m"]),
            _as_float(row["y_m"]),
            _as_float(row["crown_radius_m"]),
            left=left,
            bottom=bottom,
            resolution_m=resolution_m,
        )
        result.append(
            {
                **row,
                "point_count": count,
                "point_density": round(density, 3),
            }
        )
    return result
