"""Canopy turnover hotspots from a 2 m gain/loss grid.

The module labels contiguous gain and loss patches, drops patches below a stated
minimum area, and aggregates patch counts and sizes to the 400 m P38 grid. It does
not claim a net gain or loss; P45 showed that direction is not resolved by the
current screen.
"""

from __future__ import annotations

import io
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import numpy as np
from numpy.typing import NDArray
from PIL import Image
from pyproj import Transformer
from scipy.ndimage import label
from shapely.geometry import Polygon, mapping

from fresh_urban_forest.evidence import evidence

TURNOVER_EVIDENCE = evidence(
    "scenario",
    "connected-gain-loss-patches",
    uncertainty=(
        "Patch size depends on the 2 m change grid, the 2 m threshold, vertical-offset "
        "sensitivity, and temporary LiDAR artifacts. It is a turnover screen, not tree "
        "survival or a net change estimate."
    ),
    source="P43 2 m citywide change grid; P45 sensitivity acknowledged.",
)

TIER_COLOURS: Mapping[str, tuple[int, int, int, int]] = {
    "high": (197, 27, 125, 220),
    "medium": (239, 138, 52, 205),
    "low": (155, 190, 120, 175),
    "none": (0, 0, 0, 0),
}


@dataclass(frozen=True, slots=True)
class TurnoverCell:
    """One 400 m turnover cell.

    Attributes
    ----------
    cell_id : str
        Global cell id.
    row : int
        Grid row.
    col : int
        Grid column.
    bounds : tuple of float
        ``(left, bottom, right, top)``.
    center_lon : float
        Centre longitude.
    center_lat : float
        Centre latitude.
    area_m2 : float
        Cell area.
    gain_patch_count : int
        Gain patches at/above the minimum area.
    loss_patch_count : int
        Loss patches at/above the minimum area.
    largest_gain_patch_m2 : float
        Largest gain patch.
    largest_loss_patch_m2 : float
        Largest loss patch.
    turnover_area_m2 : float
        Sum of gain and loss patch areas.
    turnover_fraction : float
        Turnover area divided by cell area.
    turnover_tier : str
        ``high``, ``medium``, ``low``, or ``none``.
    shade_deficit : float
        P38 shade deficit.
    equity_score : float
        P38 social equity.
    gap_m2 : float
        P39 gap area.
    opportunity_tier : str
        P39 tier.
    lst_mean_c : float
        P40 mean LST.
    heat_equity_tier : str
        P40 tier.
    action_class : str
        P42 action code.
    action_label : str
        P42 action label.
    """

    cell_id: str
    row: int
    col: int
    bounds: tuple[float, float, float, float]
    center_lon: float
    center_lat: float
    area_m2: float
    gain_patch_count: int
    loss_patch_count: int
    largest_gain_patch_m2: float
    largest_loss_patch_m2: float
    turnover_area_m2: float
    turnover_fraction: float
    turnover_tier: str
    shade_deficit: float
    equity_score: float
    gap_m2: float
    opportunity_tier: str
    lst_mean_c: float
    heat_equity_tier: str
    action_class: str
    action_label: str

    def to_dict(self) -> dict[str, object]:
        """Convert the cell to a JSON-safe mapping.

        Returns
        -------
        dict
            Patch metrics and joins.
        """

        def _optional(value: float) -> float | None:
            return round(value, 4) if math.isfinite(value) else None

        return {
            "cell_id": self.cell_id,
            "row": self.row,
            "col": self.col,
            "bounds": [round(value, 3) for value in self.bounds],
            "center_lon": round(self.center_lon, 6),
            "center_lat": round(self.center_lat, 6),
            "area_m2": round(self.area_m2, 1),
            "gain_patch_count": self.gain_patch_count,
            "loss_patch_count": self.loss_patch_count,
            "largest_gain_patch_m2": round(self.largest_gain_patch_m2, 1),
            "largest_loss_patch_m2": round(self.largest_loss_patch_m2, 1),
            "turnover_area_m2": round(self.turnover_area_m2, 1),
            "turnover_fraction": round(self.turnover_fraction, 4),
            "turnover_tier": self.turnover_tier,
            "shade_deficit": _optional(self.shade_deficit),
            "equity_score": _optional(self.equity_score),
            "gap_m2": _optional(self.gap_m2),
            "opportunity_tier": self.opportunity_tier,
            "lst_mean_c": _optional(self.lst_mean_c),
            "heat_equity_tier": self.heat_equity_tier,
            "action_class": self.action_class,
            "action_label": self.action_label,
        }


def build_turnover_cells(
    *,
    change: NDArray[np.integer],
    valid: NDArray[np.bool_],
    change_bounds: tuple[float, float, float, float],
    grid_bounds: tuple[float, float, float, float],
    crs: str,
    min_patch_m2: float = 50.0,
    cell_size_m: float = 400.0,
    priority: Mapping[str, Mapping[str, object]] | None = None,
    planting: Mapping[str, Mapping[str, object]] | None = None,
    heat: Mapping[str, Mapping[str, object]] | None = None,
    action: Mapping[str, Mapping[str, object]] | None = None,
) -> tuple[TurnoverCell, ...]:
    """Build turnover cells from a 2 m change grid.

    Parameters
    ----------
    change : numpy.ndarray
        ``-1`` loss, ``1`` gain, ``0`` stable/no canopy.
    valid : numpy.ndarray
        Valid comparison mask.
    change_bounds : tuple of float
        Bounds of the change raster.
    grid_bounds : tuple of float
        Bounds of the global P38 grid.
    crs : str
        Projected CRS.
    min_patch_m2 : float
        Minimum patch area.
    cell_size_m : float
        Global cell size.
    priority, planting, heat, action : mapping or None
        Optional P38, P39, P40, and P42 cell lookups.

    Returns
    -------
    tuple of TurnoverCell
        Cells with valid change.

    Raises
    ------
    ValueError
        When shapes differ or parameters are invalid.
    """
    classes = np.asarray(change)
    observed = np.asarray(valid, dtype=np.bool_)
    if classes.shape != observed.shape or classes.ndim != 2:
        raise ValueError("change and valid must share a 2-D shape")
    if min_patch_m2 <= 0.0 or cell_size_m <= 0.0:
        raise ValueError("minimum patch and cell size must be positive")
    left, bottom, right, top = change_bounds
    grid_left, grid_bottom, grid_right, grid_top = grid_bounds
    height, width = classes.shape
    cell_x = (right - left) / width
    cell_y = (top - bottom) / height
    ncols = max(1, math.ceil((grid_right - grid_left) / cell_size_m))
    nrows = max(1, math.ceil((grid_top - grid_bottom) / cell_size_m))
    rows, cols = np.indices(classes.shape, dtype=np.float64)
    x = left + (cols + 0.5) * cell_x
    y = top - (rows + 0.5) * cell_y
    grid_x = np.clip(np.floor((x - grid_left) / cell_size_m).astype(np.int64), 0, ncols - 1)
    grid_y = np.clip(np.floor((grid_top - y) / cell_size_m).astype(np.int64), 0, nrows - 1)
    grid_id = grid_y * ncols + grid_x
    counts = np.bincount(grid_id.ravel(), minlength=nrows * ncols).astype(np.float64)
    pixel_area = cell_x * cell_y
    gain_counts, gain_largest, gain_area = _patch_stats(
        observed & (classes == 1),
        grid_id=grid_id,
        nrows=nrows,
        ncols=ncols,
        pixel_area=pixel_area,
        min_patch_m2=min_patch_m2,
    )
    loss_counts, loss_largest, loss_area = _patch_stats(
        observed & (classes == -1),
        grid_id=grid_id,
        nrows=nrows,
        ncols=ncols,
        pixel_area=pixel_area,
        min_patch_m2=min_patch_m2,
    )
    turnover = gain_area + loss_area
    turnover_fraction = np.divide(
        turnover,
        counts * pixel_area,
        out=np.zeros_like(turnover),
        where=counts > 0,
    )
    tiers = np.full(nrows * ncols, "none", dtype=object)
    active = turnover > 0.0
    if np.any(active):
        low, high = np.quantile(turnover_fraction[active], [1.0 / 3.0, 2.0 / 3.0])
        tiers[active & (turnover_fraction >= high)] = "high"
        tiers[active & (turnover_fraction >= low) & (turnover_fraction < high)] = "medium"
        tiers[active & (turnover_fraction < low)] = "low"
    priority = priority or {}
    planting = planting or {}
    heat = heat or {}
    action = action or {}
    transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    cells: list[TurnoverCell] = []
    for index in range(nrows * ncols):
        if counts[index] <= 0.0:
            continue
        row = index // ncols
        col = index % ncols
        cell_left = grid_left + col * cell_size_m
        cell_top = grid_top - row * cell_size_m
        cell_right = min(cell_left + cell_size_m, grid_right)
        cell_bottom = max(cell_top - cell_size_m, grid_bottom)
        lon, lat = transformer.transform(
            (cell_left + cell_right) / 2.0,
            (cell_top + cell_bottom) / 2.0,
        )
        cell_id = f"r{row:02d}c{col:02d}"
        p38 = priority.get(cell_id, {})
        p39 = planting.get(cell_id, {})
        p40 = heat.get(cell_id, {})
        p42 = action.get(cell_id, {})
        cells.append(
            TurnoverCell(
                cell_id=cell_id,
                row=row,
                col=col,
                bounds=(cell_left, cell_bottom, cell_right, cell_top),
                center_lon=float(lon),
                center_lat=float(lat),
                area_m2=float(counts[index] * pixel_area),
                gain_patch_count=int(gain_counts[index]),
                loss_patch_count=int(loss_counts[index]),
                largest_gain_patch_m2=float(gain_largest[index]),
                largest_loss_patch_m2=float(loss_largest[index]),
                turnover_area_m2=float(turnover[index]),
                turnover_fraction=float(turnover_fraction[index]),
                turnover_tier=str(tiers[index]),
                shade_deficit=_as_float(p38.get("shade_deficit")),
                equity_score=_as_float(p38.get("equity_score")),
                gap_m2=_as_float(p39.get("gap_m2")),
                opportunity_tier=str(p39.get("opportunity_tier", "NA")),
                lst_mean_c=_as_float(p40.get("lst_mean_c")),
                heat_equity_tier=str(p40.get("heat_equity_tier", "NA")),
                action_class=str(p42.get("action_class", "NA")),
                action_label=str(p42.get("action_label", "NA")),
            )
        )
    return tuple(cells)


def turnover_geojson(
    cells: tuple[TurnoverCell, ...],
    *,
    crs: str,
    metadata: Mapping[str, object],
) -> dict[str, object]:
    """Build a WGS84 GeoJSON FeatureCollection."""
    transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    features: list[dict[str, object]] = []
    for cell in cells:
        left, bottom, right, top = cell.bounds
        corners = (
            transformer.transform(left, bottom),
            transformer.transform(right, bottom),
            transformer.transform(right, top),
            transformer.transform(left, top),
            transformer.transform(left, bottom),
        )
        features.append(
            {
                "type": "Feature",
                "id": cell.cell_id,
                "geometry": mapping(Polygon(corners)),
                "properties": cell.to_dict(),
            }
        )
    return {
        "type": "FeatureCollection",
        "name": "canopy_turnover",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "metadata": dict(metadata),
        "features": features,
    }


def write_turnover_product(
    cells: tuple[TurnoverCell, ...],
    out_dir: Path,
    *,
    crs: str,
    metadata: Mapping[str, object],
    stem: str = "canopy_turnover",
) -> dict[str, Path]:
    """Write JSON, GeoJSON, and PNG products."""
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "fresh-urban-forest.canopy-turnover.v1",
        "metadata": dict(metadata),
        "cells": [cell.to_dict() for cell in cells],
    }
    json_path = out_dir / f"{stem}.json"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    geojson_path = out_dir / f"{stem}.geojson"
    geojson_path.write_text(
        json.dumps(turnover_geojson(cells, crs=crs, metadata=metadata), separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )
    png_path = out_dir / f"{stem}.png"
    png_path.write_bytes(turnover_png(cells))
    return {"json": json_path, "geojson": geojson_path, "png": png_path}


def turnover_png(cells: tuple[TurnoverCell, ...]) -> bytes:
    """Render turnover tiers as a transparent PNG."""
    if not cells:
        return b""
    nrows = max(cell.row for cell in cells) + 1
    ncols = max(cell.col for cell in cells) + 1
    rgba = np.zeros((nrows, ncols, 4), dtype=np.uint8)
    for cell in cells:
        rgba[cell.row, cell.col] = TIER_COLOURS.get(cell.turnover_tier, TIER_COLOURS["none"])
    image = Image.fromarray(rgba, mode="RGBA")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _patch_stats(
    mask: NDArray[np.bool_],
    *,
    grid_id: NDArray[np.int64],
    nrows: int,
    ncols: int,
    pixel_area: float,
    min_patch_m2: float,
) -> tuple[NDArray[np.int64], NDArray[np.float64], NDArray[np.float64]]:
    """Return patch count, largest patch, and total patch area by cell."""
    labels, count = label(np.asarray(mask, dtype=np.bool_), structure=np.ones((3, 3)))
    counts = np.zeros(nrows * ncols, dtype=np.int64)
    largest = np.zeros(nrows * ncols, dtype=np.float64)
    total = np.zeros(nrows * ncols, dtype=np.float64)
    if count == 0:
        return counts, largest, total
    areas = np.bincount(labels.ravel(), minlength=count + 1).astype(np.float64) * pixel_area
    keep = areas >= min_patch_m2
    flat = labels.ravel()
    _, first = np.unique(flat, return_index=True)
    first_labels = flat[first]
    valid = (first_labels > 0) & keep[first_labels]
    cell_ids = grid_id.ravel()[first[valid]]
    component_areas = areas[first_labels[valid]]
    np.add.at(total, cell_ids, component_areas)
    np.add.at(counts, cell_ids, 1)
    np.maximum.at(largest, cell_ids, component_areas)
    return counts, largest, total


def _as_float(value: object) -> float:
    """Convert a JSON value to float, returning NaN when missing."""
    if value is None:
        return float("nan")
    try:
        return float(cast(float, value))
    except (TypeError, ValueError):
        return float("nan")


__all__ = [
    "TIER_COLOURS",
    "TURNOVER_EVIDENCE",
    "TurnoverCell",
    "build_turnover_cells",
    "turnover_geojson",
    "turnover_png",
    "write_turnover_product",
]
