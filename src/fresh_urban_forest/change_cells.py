"""Observed canopy-change cells joined to shade, gap, and heat screens.

The module turns a repeat-measures 1 m change grid into 400 m cells and joins
optional P38/P39/P40 screening fields. It reports LiDAR surface change, not tree
survival, growth, ownership, species change, or causal attribution.
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
from shapely.geometry import Polygon, mapping

from fresh_urban_forest.evidence import evidence

CHANGE_CELL_EVIDENCE = evidence(
    "measured",
    "repeat-lidar-canopy-change-cells",
    uncertainty=(
        "The change is a thresholded LiDAR surface comparison. Acquisition season, "
        "point density, vertical datum, co-registration, and canopy height error can "
        "produce apparent gain or loss. It is not tree survival or a growth rate."
    ),
    source="City of Vancouver 2018 and 2022 LiDAR, 2 m canopy threshold.",
)

CHANGE_JOIN_EVIDENCE = evidence(
    "scenario",
    "change-joined-to-p38-p39-p40",
    uncertainty=(
        "The joins are descriptive overlays. A change cell with high shade, gap, or "
        "heat-equity scores does not establish cause or planting feasibility."
    ),
    source="P38 shade-equity, P39 canopy gaps, and P40 Landsat heat-equity cells.",
)

CHANGE_COLOURS: Mapping[str, tuple[int, int, int, int]] = {
    "gain": (77, 146, 33, 220),
    "loss": (197, 27, 125, 220),
    "stable": (90, 90, 90, 190),
    "no canopy": (180, 180, 180, 130),
    "none": (0, 0, 0, 0),
}


@dataclass(frozen=True, slots=True)
class ChangeCell:
    """One 400 m observed-change cell.

    Attributes
    ----------
    cell_id : str
        Global row-column identifier matching the P38 grid.
    row : int
        Global grid row.
    col : int
        Global grid column.
    bounds : tuple of float
        ``(left, bottom, right, top)`` in the projected CRS.
    center_lon : float
        Centre longitude.
    center_lat : float
        Centre latitude.
    cell_area_m2 : float
        Area of the change-raster portion in this cell.
    valid_area_m2 : float
        Area with valid observations in both dates.
    overlap_fraction : float
        Valid share of the change-raster portion.
    earlier_canopy_m2 : float
        Earlier canopy area.
    later_canopy_m2 : float
        Later canopy area.
    gain_m2 : float
        Area that became canopy.
    loss_m2 : float
        Area that stopped being canopy.
    stable_m2 : float
        Area that was canopy in both dates.
    net_m2 : float
        Later minus earlier canopy area.
    mean_height_change_m : float
        Mean later-minus-earlier height on stable canopy.
    change_class : str
        ``gain``, ``loss``, ``stable``, ``no canopy``, or ``none``.
    shade_deficit : float
        P38 shade deficit, when present.
    equity_score : float
        P38 social equity, when present.
    p38_priority_class : str
        P38 class, or ``NA``.
    gap_m2 : float
        P39 edge-gap area, when present.
    opportunity_tier : str
        P39 tier, or ``NA``.
    lst_mean_c : float
        P40 mean LST, when present.
    tespi_like : float
        P40 five-part index, when present.
    heat_equity_tier : str
        P40 tier, or ``NA``.
    """

    cell_id: str
    row: int
    col: int
    bounds: tuple[float, float, float, float]
    center_lon: float
    center_lat: float
    cell_area_m2: float
    valid_area_m2: float
    overlap_fraction: float
    earlier_canopy_m2: float
    later_canopy_m2: float
    gain_m2: float
    loss_m2: float
    stable_m2: float
    net_m2: float
    mean_height_change_m: float
    change_class: str
    shade_deficit: float
    equity_score: float
    p38_priority_class: str
    gap_m2: float
    opportunity_tier: str
    lst_mean_c: float
    tespi_like: float
    heat_equity_tier: str

    def to_dict(self) -> dict[str, object]:
        """Convert the cell to a JSON-safe mapping.

        Returns
        -------
        dict
            Cell metrics and joins.
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
            "cell_area_m2": round(self.cell_area_m2, 1),
            "valid_area_m2": round(self.valid_area_m2, 1),
            "overlap_fraction": round(self.overlap_fraction, 4),
            "earlier_canopy_m2": round(self.earlier_canopy_m2, 1),
            "later_canopy_m2": round(self.later_canopy_m2, 1),
            "gain_m2": round(self.gain_m2, 1),
            "loss_m2": round(self.loss_m2, 1),
            "stable_m2": round(self.stable_m2, 1),
            "net_m2": round(self.net_m2, 1),
            "mean_height_change_m": round(self.mean_height_change_m, 4),
            "change_class": self.change_class,
            "shade_deficit": _optional(self.shade_deficit),
            "equity_score": _optional(self.equity_score),
            "p38_priority_class": self.p38_priority_class,
            "gap_m2": _optional(self.gap_m2),
            "opportunity_tier": self.opportunity_tier,
            "lst_mean_c": _optional(self.lst_mean_c),
            "tespi_like": _optional(self.tespi_like),
            "heat_equity_tier": self.heat_equity_tier,
        }


def build_change_cells(
    *,
    earlier: NDArray[np.floating],
    later: NDArray[np.floating],
    valid: NDArray[np.bool_],
    change_bounds: tuple[float, float, float, float],
    grid_bounds: tuple[float, float, float, float],
    crs: str,
    threshold_m: float = 2.0,
    cell_size_m: float = 400.0,
    priority: Mapping[str, Mapping[str, object]] | None = None,
    planting: Mapping[str, Mapping[str, object]] | None = None,
    heat: Mapping[str, Mapping[str, object]] | None = None,
) -> tuple[ChangeCell, ...]:
    """Aggregate a 1 m change grid to global 400 m cells.

    Parameters
    ----------
    earlier : numpy.ndarray
        Earlier canopy height.
    later : numpy.ndarray
        Later canopy height.
    valid : numpy.ndarray
        Valid overlap mask.
    change_bounds : tuple of float
        Bounds of the change raster.
    grid_bounds : tuple of float
        Bounds of the global P38 analysis grid.
    crs : str
        Projected CRS.
    threshold_m : float
        Canopy threshold.
    cell_size_m : float
        Global analysis cell size.
    priority : mapping or None
        P38 cells keyed by cell id.
    planting : mapping or None
        P39 cells keyed by cell id.
    heat : mapping or None
        P40 cells keyed by cell id.

    Returns
    -------
    tuple of ChangeCell
        Cells with valid change pixels.

    Raises
    ------
    ValueError
        When array shapes differ or the cell size is not positive.
    """
    first = np.asarray(earlier, dtype=np.float64)
    second = np.asarray(later, dtype=np.float64)
    observed = np.asarray(valid, dtype=np.bool_)
    if not (first.shape == second.shape == observed.shape) or first.ndim != 2:
        raise ValueError("earlier, later, and valid must share a 2-D shape")
    if cell_size_m <= 0.0:
        raise ValueError("cell_size_m must be positive")
    left, bottom, right, top = change_bounds
    grid_left, grid_bottom, grid_right, grid_top = grid_bounds
    height, width = first.shape
    cell_x = (right - left) / width
    cell_y = (top - bottom) / height
    ncols = max(1, math.ceil((grid_right - grid_left) / cell_size_m))
    nrows = max(1, math.ceil((grid_top - grid_bottom) / cell_size_m))
    rows, cols = np.indices(first.shape, dtype=np.float64)
    x = left + (cols + 0.5) * cell_x
    y = top - (rows + 0.5) * cell_y
    grid_x = np.clip(np.floor((x - grid_left) / cell_size_m).astype(np.int64), 0, ncols - 1)
    grid_y = np.clip(np.floor((grid_top - y) / cell_size_m).astype(np.int64), 0, nrows - 1)
    grid_id = grid_y * ncols + grid_x
    counts = np.bincount(grid_id.ravel(), minlength=nrows * ncols).astype(np.float64)
    early = observed & np.isfinite(first) & (first >= threshold_m)
    late = observed & np.isfinite(second) & (second >= threshold_m)
    gain = late & ~early
    loss = early & ~late
    stable = early & late

    def _sum(mask: NDArray[np.bool_]) -> NDArray[np.float64]:
        # numpy's bincount stubs lose the concrete dtype.
        return cast(
            NDArray[np.float64],
            np.bincount(grid_id[mask], minlength=nrows * ncols).astype(np.float64)
            * (cell_x * cell_y),
        )

    earlier_area = _sum(early)
    later_area = _sum(late)
    gain_area = _sum(gain)
    loss_area = _sum(loss)
    stable_area = _sum(stable)
    valid_area = _sum(observed)
    height_change_sum = np.bincount(
        grid_id[stable],
        weights=(second[stable] - first[stable]),
        minlength=nrows * ncols,
    )
    stable_count = np.bincount(grid_id[stable], minlength=nrows * ncols).astype(np.float64)
    mean_height = np.divide(
        height_change_sum,
        stable_count,
        out=np.zeros(nrows * ncols, dtype=np.float64),
        where=stable_count > 0,
    )
    priority = priority or {}
    planting = planting or {}
    heat = heat or {}
    transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    cells: list[ChangeCell] = []
    for index in range(nrows * ncols):
        if counts[index] <= 0.0:
            continue
        row = index // ncols
        col = index % ncols
        cell_left = grid_left + col * cell_size_m
        cell_top = grid_top - row * cell_size_m
        cell_right = min(cell_left + cell_size_m, grid_right)
        cell_bottom = max(cell_top - cell_size_m, grid_bottom)
        center_x = (cell_left + cell_right) / 2.0
        center_y = (cell_top + cell_bottom) / 2.0
        lon, lat = transformer.transform(center_x, center_y)
        net = later_area[index] - earlier_area[index]
        if later_area[index] <= 0.0:
            change_class = "no canopy"
        elif earlier_area[index] > 0.0 and abs(net) / earlier_area[index] < 0.05:
            change_class = "stable"
        elif net > 0.0:
            change_class = "gain"
        else:
            change_class = "loss"
        cell_id = f"r{row:02d}c{col:02d}"
        p38 = priority.get(cell_id, {})
        p39 = planting.get(cell_id, {})
        p40 = heat.get(cell_id, {})
        cells.append(
            ChangeCell(
                cell_id=cell_id,
                row=row,
                col=col,
                bounds=(cell_left, cell_bottom, cell_right, cell_top),
                center_lon=float(lon),
                center_lat=float(lat),
                cell_area_m2=float(counts[index] * cell_x * cell_y),
                valid_area_m2=float(valid_area[index]),
                overlap_fraction=float(
                    valid_area[index] / max(counts[index] * cell_x * cell_y, 1.0)
                ),
                earlier_canopy_m2=float(earlier_area[index]),
                later_canopy_m2=float(later_area[index]),
                gain_m2=float(gain_area[index]),
                loss_m2=float(loss_area[index]),
                stable_m2=float(stable_area[index]),
                net_m2=float(net),
                mean_height_change_m=float(mean_height[index]),
                change_class=change_class,
                shade_deficit=_as_float(p38.get("shade_deficit")),
                equity_score=_as_float(p38.get("equity_score")),
                p38_priority_class=str(p38.get("priority_class", "NA")),
                gap_m2=_as_float(p39.get("gap_m2")),
                opportunity_tier=str(p39.get("opportunity_tier", "NA")),
                lst_mean_c=_as_float(p40.get("lst_mean_c")),
                tespi_like=_as_float(p40.get("tespi_like")),
                heat_equity_tier=str(p40.get("heat_equity_tier", "NA")),
            )
        )
    return tuple(cells)


def change_cells_geojson(
    cells: tuple[ChangeCell, ...],
    *,
    crs: str,
    metadata: Mapping[str, object],
) -> dict[str, object]:
    """Build a WGS84 GeoJSON FeatureCollection from change cells.

    Parameters
    ----------
    cells : tuple of ChangeCell
        Cells to export.
    crs : str
        Projected CRS.
    metadata : mapping
        Product metadata.

    Returns
    -------
    dict
        GeoJSON FeatureCollection.
    """
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
        "name": "canopy_change",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "metadata": dict(metadata),
        "features": features,
    }


def write_change_cells(
    cells: tuple[ChangeCell, ...],
    out_dir: Path,
    *,
    crs: str,
    metadata: Mapping[str, object],
    stem: str = "canopy_change",
) -> dict[str, Path]:
    """Write JSON, GeoJSON, and PNG products for change cells.

    Parameters
    ----------
    cells : tuple of ChangeCell
        Change cells.
    out_dir : Path
        Destination directory.
    crs : str
        Projected CRS.
    metadata : mapping
        Product metadata.
    stem : str
        Output stem.

    Returns
    -------
    dict of str to Path
        Written paths.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "fresh-urban-forest.canopy-change.v1",
        "metadata": dict(metadata),
        "cells": [cell.to_dict() for cell in cells],
    }
    json_path = out_dir / f"{stem}.json"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    geojson_path = out_dir / f"{stem}.geojson"
    geojson_path.write_text(
        json.dumps(
            change_cells_geojson(cells, crs=crs, metadata=metadata),
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    png_path = out_dir / f"{stem}.png"
    png_path.write_bytes(change_cells_png(cells))
    return {"json": json_path, "geojson": geojson_path, "png": png_path}


def change_cells_png(cells: tuple[ChangeCell, ...]) -> bytes:
    """Render change classes as a transparent PNG.

    Parameters
    ----------
    cells : tuple of ChangeCell
        Change cells.

    Returns
    -------
    bytes
        PNG bytes.
    """
    if not cells:
        return b""
    nrows = max(cell.row for cell in cells) + 1
    ncols = max(cell.col for cell in cells) + 1
    rgba = np.zeros((nrows, ncols, 4), dtype=np.uint8)
    for cell in cells:
        rgba[cell.row, cell.col] = CHANGE_COLOURS.get(cell.change_class, CHANGE_COLOURS["none"])
    image = Image.fromarray(rgba, mode="RGBA")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _as_float(value: object) -> float:
    """Convert a JSON value to float, returning NaN when missing."""
    if value is None:
        return float("nan")
    try:
        return float(cast(float, value))
    except (TypeError, ValueError):
        return float("nan")


__all__ = [
    "CHANGE_CELL_EVIDENCE",
    "CHANGE_COLOURS",
    "CHANGE_JOIN_EVIDENCE",
    "ChangeCell",
    "build_change_cells",
    "change_cells_geojson",
    "change_cells_png",
    "write_change_cells",
]
