"""Integrated canopy-action screening from P38-P41 cells.

The screen joins shade/equity, canopy gaps, heat equity, and observed change by
global 400 m cell id and assigns a deterministic action label. It is a
decision-support screen, not a planting plan, cost model, utility check,
ownership claim, or causal forecast.
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
from PIL import Image
from pyproj import Transformer
from shapely.geometry import Polygon, mapping

from fresh_urban_forest.evidence import evidence

ACTION_EVIDENCE = evidence(
    "scenario",
    "p38-p41-action-matrix",
    uncertainty=(
        "The action label is a deterministic screening rule over four relative "
        "products. It is not a planting plan, cost or utility check, ownership "
        "claim, causal forecast, or field-validated recommendation."
    ),
    source="P38 shade/equity, P39 gaps, P40 heat equity, and P41 observed change.",
)

ACTION_LABELS: Mapping[str, str] = {
    "plant_cool": "plant + cool",
    "structural_shade": "structural shade / retain",
    "expand_canopy": "expand canopy",
    "protect_loss": "protect / investigate loss",
    "monitor": "monitor",
}

ACTION_COLOURS: Mapping[str, tuple[int, int, int, int]] = {
    "plant_cool": (55, 126, 34, 225),
    "structural_shade": (49, 130, 189, 215),
    "expand_canopy": (230, 145, 30, 205),
    "protect_loss": (197, 27, 125, 225),
    "monitor": (140, 140, 140, 170),
    "none": (0, 0, 0, 0),
}


@dataclass(frozen=True, slots=True)
class ActionCell:
    """One 400 m integrated action cell.

    Attributes
    ----------
    cell_id : str
        Global grid cell id.
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
    shade_deficit : float
        P38 shade deficit.
    equity_score : float
        P38 social equity.
    p38_priority_class : str
        P38 class.
    gap_m2 : float
        P39 edge-gap area.
    street_gap_m2 : float
        P39 street-adjacent gap area.
    opportunity_tier : str
        P39 tier.
    lst_mean_c : float
        P40 mean LST.
    tespi_like : float
        P40 five-part index.
    heat_equity_tier : str
        P40 tier.
    change_class : str
        P41 class or ``not observed``.
    net_m2 : float
        P41 net change, or NaN.
    gain_m2 : float
        P41 gain, or NaN.
    loss_m2 : float
        P41 loss, or NaN.
    change_observed : bool
        Whether P41 covers the cell.
    action_class : str
        Action code.
    action_label : str
        Human-readable action label.
    """

    cell_id: str
    row: int
    col: int
    bounds: tuple[float, float, float, float]
    center_lon: float
    center_lat: float
    shade_deficit: float
    equity_score: float
    p38_priority_class: str
    gap_m2: float
    street_gap_m2: float
    opportunity_tier: str
    lst_mean_c: float
    tespi_like: float
    heat_equity_tier: str
    change_class: str
    net_m2: float
    gain_m2: float
    loss_m2: float
    change_observed: bool
    action_class: str
    action_label: str

    def to_dict(self) -> dict[str, object]:
        """Convert the cell to a JSON-safe mapping.

        Returns
        -------
        dict
            Cell metrics, change flags, and action.
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
            "shade_deficit": _optional(self.shade_deficit),
            "equity_score": _optional(self.equity_score),
            "p38_priority_class": self.p38_priority_class,
            "gap_m2": _optional(self.gap_m2),
            "street_gap_m2": _optional(self.street_gap_m2),
            "opportunity_tier": self.opportunity_tier,
            "lst_mean_c": _optional(self.lst_mean_c),
            "tespi_like": _optional(self.tespi_like),
            "heat_equity_tier": self.heat_equity_tier,
            "change_class": self.change_class,
            "net_m2": _optional(self.net_m2),
            "gain_m2": _optional(self.gain_m2),
            "loss_m2": _optional(self.loss_m2),
            "change_observed": self.change_observed,
            "action_class": self.action_class,
            "action_label": self.action_label,
        }


def build_action_cells(
    *,
    priority: Mapping[str, Mapping[str, object]],
    planting: Mapping[str, Mapping[str, object]],
    heat: Mapping[str, Mapping[str, object]],
    change: Mapping[str, Mapping[str, object]],
    crs: str,
) -> tuple[ActionCell, ...]:
    """Join P38-P41 cells and assign deterministic action labels.

    Parameters
    ----------
    priority : mapping
        P38 cells keyed by cell id.
    planting : mapping
        P39 cells keyed by cell id.
    heat : mapping
        P40 cells keyed by cell id.
    change : mapping
        P41 cells keyed by cell id.
    crs : str
        Projected CRS.

    Returns
    -------
    tuple of ActionCell
        Joined action cells.

    Raises
    ------
    ValueError
        When no cell ids are available.
    """
    ids = sorted(set(priority) | set(planting) | set(heat))
    if not ids:
        raise ValueError("no P38/P39/P40 cells were supplied")
    tespi_values = [
        _as_float(heat.get(cell_id, {}).get("tespi_like")) for cell_id in ids if cell_id in heat
    ]
    gap_values = [
        _as_float(planting.get(cell_id, {}).get("gap_m2")) for cell_id in ids if cell_id in planting
    ]
    tespi_median = float(np.nanmedian(tespi_values)) if tespi_values else 0.5
    gap_median = float(np.nanmedian(gap_values)) if gap_values else 0.0
    transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    cells: list[ActionCell] = []
    for cell_id in ids:
        p38 = priority.get(cell_id, {})
        p39 = planting.get(cell_id, {})
        p40 = heat.get(cell_id, {})
        p41 = change.get(cell_id)
        bounds_raw = p38.get("bounds") or p39.get("bounds") or p40.get("bounds")
        if not isinstance(bounds_raw, list) or len(bounds_raw) != 4:
            continue
        left, bottom, right, top = (float(value) for value in bounds_raw)
        lon, lat = transformer.transform((left + right) / 2.0, (bottom + top) / 2.0)
        heat_tier = str(p40.get("heat_equity_tier", "NA"))
        tespi = _as_float(p40.get("tespi_like"))
        high_heat = heat_tier == "high" or (math.isfinite(tespi) and tespi >= tespi_median)
        gap = _as_float(p39.get("gap_m2"))
        gap_tier = str(p39.get("opportunity_tier", "NA"))
        high_gap = gap_tier == "high" or (math.isfinite(gap) and gap >= gap_median)
        observed = p41 is not None
        change_class = str(p41.get("change_class", "not observed")) if p41 else "not observed"
        action_class = _action(high_heat, high_gap, change_class)
        cells.append(
            ActionCell(
                cell_id=cell_id,
                row=int(cast(int, p38.get("row", p39.get("row", p40.get("row", 0))))),
                col=int(cast(int, p38.get("col", p39.get("col", p40.get("col", 0))))),
                bounds=(left, bottom, right, top),
                center_lon=float(lon),
                center_lat=float(lat),
                shade_deficit=_as_float(p38.get("shade_deficit")),
                equity_score=_as_float(p38.get("equity_score")),
                p38_priority_class=str(p38.get("priority_class", "NA")),
                gap_m2=gap,
                street_gap_m2=_as_float(p39.get("street_gap_m2")),
                opportunity_tier=gap_tier,
                lst_mean_c=_as_float(p40.get("lst_mean_c")),
                tespi_like=tespi,
                heat_equity_tier=heat_tier,
                change_class=change_class,
                net_m2=_as_float(p41.get("net_m2")) if p41 else float("nan"),
                gain_m2=_as_float(p41.get("gain_m2")) if p41 else float("nan"),
                loss_m2=_as_float(p41.get("loss_m2")) if p41 else float("nan"),
                change_observed=observed,
                action_class=action_class,
                action_label=ACTION_LABELS[action_class],
            )
        )
    return tuple(cells)


def action_geojson(
    cells: tuple[ActionCell, ...],
    *,
    crs: str,
    metadata: Mapping[str, object],
) -> dict[str, object]:
    """Build a WGS84 GeoJSON FeatureCollection from action cells.

    Parameters
    ----------
    cells : tuple of ActionCell
        Action cells.
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
        "name": "canopy_action",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "metadata": dict(metadata),
        "features": features,
    }


def write_action_product(
    cells: tuple[ActionCell, ...],
    out_dir: Path,
    *,
    crs: str,
    metadata: Mapping[str, object],
    stem: str = "canopy_action",
) -> dict[str, Path]:
    """Write JSON, GeoJSON, and PNG products for action cells.

    Parameters
    ----------
    cells : tuple of ActionCell
        Action cells.
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
        "schema_version": "fresh-urban-forest.canopy-action.v1",
        "metadata": dict(metadata),
        "cells": [cell.to_dict() for cell in cells],
    }
    json_path = out_dir / f"{stem}.json"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    geojson_path = out_dir / f"{stem}.geojson"
    geojson_path.write_text(
        json.dumps(
            action_geojson(cells, crs=crs, metadata=metadata),
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    png_path = out_dir / f"{stem}.png"
    png_path.write_bytes(action_png(cells))
    return {"json": json_path, "geojson": geojson_path, "png": png_path}


def action_png(cells: tuple[ActionCell, ...]) -> bytes:
    """Render action classes as a transparent PNG.

    Parameters
    ----------
    cells : tuple of ActionCell
        Action cells.

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
        rgba[cell.row, cell.col] = ACTION_COLOURS.get(cell.action_class, ACTION_COLOURS["none"])
    image = Image.fromarray(rgba, mode="RGBA")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _action(high_heat: bool, high_gap: bool, change_class: str) -> str:
    """Return the deterministic action code."""
    if change_class == "loss":
        return "protect_loss"
    if high_heat and high_gap:
        return "plant_cool"
    if high_heat:
        return "structural_shade"
    if high_gap:
        return "expand_canopy"
    return "monitor"


def _as_float(value: object) -> float:
    """Convert a JSON value to float, returning NaN when missing."""
    if value is None:
        return float("nan")
    try:
        return float(cast(float, value))
    except (TypeError, ValueError):
        return float("nan")


__all__ = [
    "ACTION_COLOURS",
    "ACTION_EVIDENCE",
    "ACTION_LABELS",
    "ActionCell",
    "action_geojson",
    "action_png",
    "build_action_cells",
    "write_action_product",
]
