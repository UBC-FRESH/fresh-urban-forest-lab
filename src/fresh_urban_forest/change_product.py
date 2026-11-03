"""Build a portable observed-change product from two terrain grids.

The product is a small directory with a JSON summary, a class grid, and a transparent PNG
that the browser can place over the campus map with the same bounds as the dataset.
"""

from __future__ import annotations

import io
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
from PIL import Image

from fresh_urban_forest.change import canopy_change, change_grid
from fresh_urban_forest.models import TerrainGrid
from fresh_urban_forest.terrain import unproject_xy

CHANGE_SCHEMA_VERSION = "fresh-urban-forest.change.v1"
LEGEND: tuple[tuple[str, str], ...] = (
    ("loss", "#c84a3f"),
    ("stable canopy", "#2f6b4f"),
    ("gain", "#8ebf5a"),
    ("no canopy", "#d9dfd2"),
)


def build_change_product(
    earlier: TerrainGrid,
    later: TerrainGrid,
    out_dir: Path,
    *,
    threshold_m: float = 2.0,
    earlier_label: str = "earlier",
    later_label: str = "later",
) -> Path:
    """Write a change summary, class grid, and PNG overlay.

    Parameters
    ----------
    earlier : TerrainGrid
        Earlier canopy-height grid.
    later : TerrainGrid
        Later canopy-height grid on the same bounds and shape.
    out_dir : Path
        Destination directory.
    threshold_m : float
        Minimum canopy height in metres.
    earlier_label : str
        Human-readable earlier label, for example ``2016 LidarBC``.
    later_label : str
        Human-readable later label, for example ``2021 UBC LiDAR``.

    Returns
    -------
    Path
        The written ``change.json`` path.

    Raises
    ------
    ValueError
        When the grids do not share a shape or bounds.
    """
    if earlier.canopy_height is None or later.canopy_height is None:
        raise ValueError("both grids need a canopy_height array")
    if earlier.canopy_height.shape != later.canopy_height.shape:
        raise ValueError("earlier and later canopy grids must share a shape")
    if earlier.bounds != later.bounds:
        raise ValueError("earlier and later grids must share bounds")
    cell_area = (earlier.bounds[2] - earlier.bounds[0]) * (earlier.bounds[3] - earlier.bounds[1])
    cell_area /= earlier.width * earlier.height
    summary = canopy_change(
        earlier.canopy_height,
        later.canopy_height,
        threshold_m=threshold_m,
        cell_area_m2=cell_area,
    )
    classes = change_grid(
        earlier.canopy_height,
        later.canopy_height,
        threshold_m=threshold_m,
    )
    valid = np.isfinite(earlier.canopy_height) & np.isfinite(later.canopy_height)
    valid_area = float(np.count_nonzero(valid) * cell_area)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_png(
        classes,
        valid,
        earlier.canopy_height,
        later.canopy_height,
        threshold_m,
        out_dir / "change.png",
    )
    np.savez_compressed(
        out_dir / "change_grid.npz",
        change=classes,
        earlier=earlier.canopy_height,
        later=later.canopy_height,
        elevation=earlier.elevation,
        valid=valid,
    )
    west, south = unproject_xy(earlier.bounds[0], earlier.bounds[1], earlier.crs)
    east, north = unproject_xy(earlier.bounds[2], earlier.bounds[3], earlier.crs)
    valid_bounds, valid_bounds_wgs84 = _valid_bounds(earlier, valid)
    payload = {
        "schema_version": CHANGE_SCHEMA_VERSION,
        "earlier_label": earlier_label,
        "later_label": later_label,
        "crs": earlier.crs,
        "bounds": list(earlier.bounds),
        "bounds_wgs84": [min(west, east), min(south, north), max(west, east), max(south, north)],
        "valid_bounds": list(valid_bounds),
        "valid_bounds_wgs84": list(valid_bounds_wgs84),
        "width": earlier.width,
        "height": earlier.height,
        "cell_area_m2": round(cell_area, 6),
        "valid_overlap_m2": round(valid_area, 3),
        "threshold_m": threshold_m,
        "metrics": asdict(summary),
        "legend": [{"label": label, "colour": colour} for label, colour in LEGEND],
        "files": {
            "summary": "change.json",
            "png": "change.png",
            "grid": "change_grid.npz",
        },
    }
    path = out_dir / "change.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _valid_bounds(
    grid: TerrainGrid,
    valid: np.ndarray,
) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float]]:
    """Return projected and WGS84 bounds around valid change cells.

    Parameters
    ----------
    grid : TerrainGrid
        Grid that defines the transform.
    valid : numpy.ndarray
        Boolean validity mask.

    Returns
    -------
    tuple
        Projected bounds and WGS84 bounds. When no cell is valid, both are the full grid.
    """
    rows, cols = np.nonzero(valid)
    if rows.size == 0:
        return (grid.bounds, _wgs84_bounds(grid, grid.bounds))
    left, bottom, right, top = grid.bounds
    dx = (right - left) / grid.width
    dy = (top - bottom) / grid.height
    cell_bounds = (
        left + float(cols.min()) * dx,
        top - float(rows.max() + 1) * dy,
        left + float(cols.max() + 1) * dx,
        top - float(rows.min()) * dy,
    )
    return (cell_bounds, _wgs84_bounds(grid, cell_bounds))


def _wgs84_bounds(
    grid: TerrainGrid,
    bounds: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    """Convert projected bounds to WGS84.

    Parameters
    ----------
    grid : TerrainGrid
        Grid that supplies the CRS.
    bounds : tuple of float
        Projected bounds.

    Returns
    -------
    tuple of float
        WGS84 bounds.
    """
    west, south = unproject_xy(bounds[0], bounds[1], grid.crs)
    east, north = unproject_xy(bounds[2], bounds[3], grid.crs)
    return (min(west, east), min(south, north), max(west, east), max(south, north))


def _write_png(
    classes: np.ndarray,
    valid: np.ndarray,
    earlier: np.ndarray,
    later: np.ndarray,
    threshold_m: float,
    path: Path,
) -> None:
    """Write a transparent change-class PNG.

    Parameters
    ----------
    classes : numpy.ndarray
        ``-1`` loss, ``1`` gain, ``0`` stable or no canopy.
    valid : numpy.ndarray
        Cells with both dates.
    earlier : numpy.ndarray
        Earlier canopy height.
    later : numpy.ndarray
        Later canopy height.
    threshold_m : float
        Canopy threshold.
    path : Path
        Destination PNG.
    """
    rgba = np.zeros((classes.shape[0], classes.shape[1], 4), dtype=np.uint8)
    earlier_canopy = valid & (np.nan_to_num(earlier, nan=0.0) >= threshold_m)
    later_canopy = valid & (np.nan_to_num(later, nan=0.0) >= threshold_m)
    rgba[valid & ~earlier_canopy & ~later_canopy] = (217, 223, 210, 90)
    rgba[valid & earlier_canopy & later_canopy] = (47, 107, 79, 220)
    rgba[classes == -1] = (200, 74, 63, 235)
    rgba[classes == 1] = (142, 191, 90, 235)
    image = Image.fromarray(rgba, mode="RGBA")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    path.write_bytes(buffer.getvalue())
