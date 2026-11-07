"""Canopy-gap and above-ground planting-opportunity screening.

The screen finds open, uncanopied ground from a public LiDAR CHM, removes
buildings, water, road surfaces, and steep slopes, and separates edge gaps
(near existing canopy) from interior open ground. It reports a gross
crown-slot envelope and a count of contiguous gap sites. It does not model
underground utilities, ownership, access, soil volume, irrigation, cost, or
field conditions, so the result is not a planting plan.
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
from scipy.ndimage import distance_transform_edt, label
from shapely.geometry import Polygon, mapping

from fresh_urban_forest.evidence import Evidence, evidence

GAP_EVIDENCE = evidence(
    "physics",
    "lidar-open-ground-gap-screen",
    uncertainty=(
        "Open ground is inferred from a resampled LiDAR canopy surface and public "
        "building, water, and road masks. It is not a survey of plantable soil, access, "
        "ownership, utilities, or maintenance feasibility."
    ),
    source="City of Vancouver LiDAR + OSM road centrelines; open-data screening only.",
)

OPPORTUNITY_EVIDENCE = evidence(
    "scenario",
    "gap-area-times-shade-equity",
    uncertainty=(
        "The score multiplies gap area by the P38 shade deficit and Census equity score. "
        "It is a relative screen, not a benefit-cost model or a planting permit."
    ),
    source="P38 shade-equity screen plus public canopy-gap masks.",
)

SMALL_CROWN_AREA_M2 = math.pi * (4.1 / 2.0) ** 2
MEDIUM_CROWN_AREA_M2 = math.pi * (7.6 / 2.0) ** 2
LARGE_CROWN_AREA_M2 = math.pi * (15.3 / 2.0) ** 2
SMALL_MIN_AREA_M2 = 13.0
MEDIUM_MIN_AREA_M2 = 45.0
LARGE_MIN_AREA_M2 = 185.0
DEFAULT_GAP_DISTANCE_M = 15.0
DEFAULT_STREET_DISTANCE_M = 10.0
DEFAULT_SLOPE_MAX_DEG = 15.0
DEFAULT_CANOPY_THRESHOLD_M = 2.0
DEFAULT_SITE_MIN_AREA_M2 = 45.0

TIER_COLOURS: Mapping[str, tuple[int, int, int, int]] = {
    "high": (202, 76, 24, 220),
    "medium": (244, 165, 56, 205),
    "low": (155, 190, 120, 175),
    "none": (0, 0, 0, 0),
}


@dataclass(frozen=True, slots=True)
class GapMasks:
    """Raster masks and summary for the canopy-gap screen.

    Attributes
    ----------
    open_ground : numpy.ndarray
        Open, uncanopied, non-building, non-water, non-road, gentle-slope ground.
    gap : numpy.ndarray
        Open ground within the canopy-gap distance of existing canopy.
    street_gap : numpy.ndarray
        Gap pixels within the street-adjacent distance of a road centreline.
    interior_open : numpy.ndarray
        Open ground farther than the gap distance from canopy.
    slope_deg : numpy.ndarray
        Terrain slope in degrees.
    summary : dict
        Area and fraction summary.
    evidence : Evidence
        Method and uncertainty.
    """

    open_ground: NDArray[np.bool_]
    gap: NDArray[np.bool_]
    street_gap: NDArray[np.bool_]
    interior_open: NDArray[np.bool_]
    slope_deg: NDArray[np.float32]
    summary: dict[str, float]
    evidence: Evidence

    def to_dict(self) -> dict[str, object]:
        """Convert the summary and evidence to a JSON-safe mapping.

        Returns
        -------
        dict
            Summary and evidence.
        """
        return {"summary": self.summary, "evidence": self.evidence.to_dict()}


@dataclass(frozen=True, slots=True)
class OpportunityCell:
    """One 400 m planting-opportunity cell.

    Attributes
    ----------
    cell_id : str
        Stable row-column identifier.
    row : int
        Grid row.
    col : int
        Grid column.
    bounds : tuple of float
        ``(left, bottom, right, top)`` in the projected CRS.
    center_lon : float
        Centre longitude.
    center_lat : float
        Centre latitude.
    area_m2 : float
        Cell area inside the raster bounds.
    open_ground_m2 : float
        Open ground area.
    gap_m2 : float
        Edge-gap area within the canopy-gap distance.
    street_gap_m2 : float
        Edge-gap area within the street-adjacent distance.
    interior_open_m2 : float
        Open ground beyond the canopy-gap distance.
    gap_sites : int
        Contiguous gap components at least the site minimum area.
    street_gap_sites : int
        Contiguous street-adjacent gap components at least the site minimum area.
    capacity_small_upper : int
        Upper bound from gap area divided by small-crown area.
    capacity_medium_upper : int
        Upper bound from gap area divided by medium-crown area.
    capacity_large_upper : int
        Upper bound from gap area divided by large-crown area.
    shade_deficit : float
        P38 shade deficit, or ``nan`` when absent.
    equity_score : float
        P38 social-equity score, or ``nan`` when absent.
    priority_class : str
        P38 class, or ``NA`` when absent.
    opportunity_score : float
        Relative gap x shade x equity score.
    opportunity_tier : str
        ``high``, ``medium``, ``low``, or ``none``.
    """

    cell_id: str
    row: int
    col: int
    bounds: tuple[float, float, float, float]
    center_lon: float
    center_lat: float
    area_m2: float
    open_ground_m2: float
    gap_m2: float
    street_gap_m2: float
    interior_open_m2: float
    gap_sites: int
    street_gap_sites: int
    capacity_small_upper: int
    capacity_medium_upper: int
    capacity_large_upper: int
    shade_deficit: float
    equity_score: float
    priority_class: str
    opportunity_score: float
    opportunity_tier: str

    def to_dict(self) -> dict[str, object]:
        """Convert the cell to a JSON-safe mapping.

        Returns
        -------
        dict
            Cell metrics and tier.
        """
        return {
            "cell_id": self.cell_id,
            "row": self.row,
            "col": self.col,
            "bounds": [round(value, 3) for value in self.bounds],
            "center_lon": round(self.center_lon, 6),
            "center_lat": round(self.center_lat, 6),
            "area_m2": round(self.area_m2, 1),
            "open_ground_m2": round(self.open_ground_m2, 1),
            "gap_m2": round(self.gap_m2, 1),
            "street_gap_m2": round(self.street_gap_m2, 1),
            "interior_open_m2": round(self.interior_open_m2, 1),
            "gap_sites": self.gap_sites,
            "street_gap_sites": self.street_gap_sites,
            "capacity_small_upper": self.capacity_small_upper,
            "capacity_medium_upper": self.capacity_medium_upper,
            "capacity_large_upper": self.capacity_large_upper,
            "shade_deficit": (
                round(self.shade_deficit, 4) if math.isfinite(self.shade_deficit) else None
            ),
            "equity_score": (
                round(self.equity_score, 4) if math.isfinite(self.equity_score) else None
            ),
            "priority_class": self.priority_class,
            "opportunity_score": round(self.opportunity_score, 5),
            "opportunity_tier": self.opportunity_tier,
        }


def slope_degrees(
    dem: NDArray[np.floating],
    cell_size_m: float,
) -> NDArray[np.float32]:
    """Calculate terrain slope in degrees.

    Parameters
    ----------
    dem : numpy.ndarray
        Ground elevation, shape ``(height, width)``.
    cell_size_m : float
        Raster cell size in metres.

    Returns
    -------
    numpy.ndarray
        Slope in degrees.

    Raises
    ------
    ValueError
        When the raster is not two-dimensional or the cell size is not positive.
    """
    array = np.asarray(dem, dtype=np.float64)
    if array.ndim != 2:
        raise ValueError("dem must be two-dimensional")
    if cell_size_m <= 0.0:
        raise ValueError("cell_size_m must be positive")
    filled = np.nan_to_num(array, nan=0.0)
    gradient_y, gradient_x = np.gradient(filled, cell_size_m, cell_size_m)
    # numpy gradient stubs lose the concrete dtype.
    return cast(
        NDArray[np.float32],
        np.degrees(np.arctan(np.hypot(gradient_x, gradient_y))).astype(np.float32),
    )


def build_gap_masks(
    *,
    dem: NDArray[np.floating],
    canopy_height: NDArray[np.floating],
    building_mask: NDArray[np.bool_],
    water_mask: NDArray[np.bool_],
    road_surface_mask: NDArray[np.bool_],
    road_center_mask: NDArray[np.bool_],
    cell_size_m: float,
    canopy_threshold_m: float = DEFAULT_CANOPY_THRESHOLD_M,
    gap_distance_m: float = DEFAULT_GAP_DISTANCE_M,
    street_distance_m: float = DEFAULT_STREET_DISTANCE_M,
    slope_max_deg: float = DEFAULT_SLOPE_MAX_DEG,
) -> GapMasks:
    """Build open-ground and canopy-gap masks.

    Parameters
    ----------
    dem : numpy.ndarray
        Ground elevation.
    canopy_height : numpy.ndarray
        Canopy height above ground.
    building_mask : numpy.ndarray
        Building footprint mask.
    water_mask : numpy.ndarray
        Water mask.
    road_surface_mask : numpy.ndarray
        Road-surface exclusion mask.
    road_center_mask : numpy.ndarray
        Road-centreline mask used for the street-adjacency distance.
    cell_size_m : float
        Raster cell size in metres.
    canopy_threshold_m : float
        Minimum canopy height.
    gap_distance_m : float
        Maximum distance from canopy for an edge gap.
    street_distance_m : float
        Maximum distance from a road centreline for a street-adjacent gap.
    slope_max_deg : float
        Maximum plantable slope used in the screen.

    Returns
    -------
    GapMasks
        Boolean masks and summary.

    Raises
    ------
    ValueError
        When shapes differ or a distance is negative.
    """
    shape = np.asarray(dem).shape
    inputs = (canopy_height, building_mask, water_mask, road_surface_mask, road_center_mask)
    if any(np.asarray(value).shape != shape for value in inputs):
        raise ValueError("all masks must share the DEM shape")
    if gap_distance_m < 0.0 or street_distance_m < 0.0:
        raise ValueError("distances must be non-negative")
    canopy = (
        np.nan_to_num(np.asarray(canopy_height, dtype=np.float64), nan=0.0) >= canopy_threshold_m
    )
    slope = slope_degrees(dem, cell_size_m)
    open_ground = (
        ~canopy
        & ~np.asarray(building_mask, dtype=np.bool_)
        & ~np.asarray(water_mask, dtype=np.bool_)
        & ~np.asarray(road_surface_mask, dtype=np.bool_)
        & (slope <= slope_max_deg)
    )
    distance_to_canopy = distance_transform_edt(~canopy) * cell_size_m
    gap = open_ground & (distance_to_canopy <= gap_distance_m)
    interior = open_ground & (distance_to_canopy > gap_distance_m)
    road_center = np.asarray(road_center_mask, dtype=np.bool_)
    distance_to_road = distance_transform_edt(~road_center) * cell_size_m
    street_gap = gap & (distance_to_road <= street_distance_m)
    pixel_area = cell_size_m * cell_size_m
    total_area = max(shape[0] * shape[1] * pixel_area, 1.0)
    summary = {
        "open_ground_m2": float(open_ground.sum() * pixel_area),
        "gap_m2": float(gap.sum() * pixel_area),
        "street_gap_m2": float(street_gap.sum() * pixel_area),
        "interior_open_m2": float(interior.sum() * pixel_area),
        "open_ground_fraction": float(open_ground.sum() * pixel_area / total_area),
        "gap_fraction": float(gap.sum() * pixel_area / total_area),
        "street_gap_share": float(street_gap.sum() / max(gap.sum(), 1)),
        "slope_max_deg": slope_max_deg,
        "gap_distance_m": gap_distance_m,
        "street_distance_m": street_distance_m,
    }
    return GapMasks(
        open_ground=np.asarray(open_ground, dtype=np.bool_),
        gap=np.asarray(gap, dtype=np.bool_),
        street_gap=np.asarray(street_gap, dtype=np.bool_),
        interior_open=np.asarray(interior, dtype=np.bool_),
        slope_deg=slope,
        summary=summary,
        evidence=GAP_EVIDENCE,
    )


def build_opportunity_grid(
    masks: GapMasks,
    *,
    bounds: tuple[float, float, float, float],
    crs: str,
    priority: Mapping[str, Mapping[str, object]] | None = None,
    cell_size_m: float = 400.0,
    site_min_area_m2: float = DEFAULT_SITE_MIN_AREA_M2,
) -> tuple[OpportunityCell, ...]:
    """Aggregate gap masks to 400 m opportunity cells.

    Parameters
    ----------
    masks : GapMasks
        Output of :func:`build_gap_masks`.
    bounds : tuple of float
        ``(left, bottom, right, top)`` in the projected CRS.
    crs : str
        Projected CRS.
    priority : mapping or None
        P38 cells keyed by ``cell_id`` with ``shade_deficit``, ``equity_score``,
        and ``priority_class``.
    cell_size_m : float
        Analysis cell size.
    site_min_area_m2 : float
        Minimum contiguous gap area counted as one site.

    Returns
    -------
    tuple of OpportunityCell
        Populated cells, ordered by row and column.

    Raises
    ------
    ValueError
        When the cell size is not positive.
    """
    if cell_size_m <= 0.0:
        raise ValueError("cell_size_m must be positive")
    shape = masks.open_ground.shape
    height, width = shape
    left, bottom, right, top = bounds
    cell_x = (right - left) / width
    cell_y = (top - bottom) / height
    ncols = max(1, math.ceil((right - left) / cell_size_m))
    nrows = max(1, math.ceil((top - bottom) / cell_size_m))
    rows, cols = np.indices(shape, dtype=np.float64)
    x = left + (cols + 0.5) * cell_x
    y = top - (rows + 0.5) * cell_y
    grid_x = np.clip(np.floor((x - left) / cell_size_m).astype(np.int64), 0, ncols - 1)
    grid_y = np.clip(np.floor((top - y) / cell_size_m).astype(np.int64), 0, nrows - 1)
    grid_id = grid_y * ncols + grid_x
    counts = np.bincount(grid_id.ravel(), minlength=nrows * ncols).astype(np.float64)
    pixel_area = cell_x * cell_y

    def _sum(values: NDArray[np.bool_] | NDArray[np.floating]) -> NDArray[np.float64]:
        return np.bincount(
            grid_id.ravel(),
            weights=np.asarray(values, dtype=np.float64).ravel(),
            minlength=nrows * ncols,
        )

    open_area = _sum(masks.open_ground) * pixel_area
    gap_area = _sum(masks.gap) * pixel_area
    street_area = _sum(masks.street_gap) * pixel_area
    interior_area = _sum(masks.interior_open) * pixel_area
    gap_sites = _component_sites(
        masks.gap,
        grid_id=grid_id,
        nrows=nrows,
        ncols=ncols,
        pixel_area=pixel_area,
        min_area_m2=site_min_area_m2,
    )
    street_sites = _component_sites(
        masks.street_gap,
        grid_id=grid_id,
        nrows=nrows,
        ncols=ncols,
        pixel_area=pixel_area,
        min_area_m2=site_min_area_m2,
    )
    capacity_small = np.floor(gap_area / SMALL_CROWN_AREA_M2).astype(np.int64)
    capacity_medium = np.floor(gap_area / MEDIUM_CROWN_AREA_M2).astype(np.int64)
    capacity_large = np.floor(gap_area / LARGE_CROWN_AREA_M2).astype(np.int64)

    shade = np.full(nrows * ncols, np.nan, dtype=np.float64)
    equity = np.full(nrows * ncols, np.nan, dtype=np.float64)
    priority_class = ["NA"] * (nrows * ncols)
    if priority:
        for index in range(nrows * ncols):
            cell_id = _cell_id(index, ncols)
            priority_row = priority.get(cell_id)
            if priority_row is None:
                continue
            shade[index] = _as_float(priority_row.get("shade_deficit"))
            equity[index] = _as_float(priority_row.get("equity_score"))
            priority_class[index] = str(priority_row.get("priority_class", "NA"))

    gap_fraction = np.divide(
        gap_area,
        counts * pixel_area,
        out=np.zeros_like(gap_area),
        where=counts > 0,
    )
    need = np.where(
        np.isfinite(shade) & np.isfinite(equity),
        shade * (0.5 + equity),
        0.5,
    )
    score = gap_fraction * need
    valid = (counts > 0) & (gap_area > 0.0)
    tiers = np.full(nrows * ncols, "none", dtype=object)
    if np.any(valid):
        low, high = np.quantile(score[valid], [1.0 / 3.0, 2.0 / 3.0])
        tiers[valid & (score >= high)] = "high"
        tiers[valid & (score >= low) & (score < high)] = "medium"
        tiers[valid & (score < low)] = "low"

    cells: list[OpportunityCell] = []
    transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    for index in range(nrows * ncols):
        if counts[index] <= 0.0 or open_area[index] <= 0.0:
            continue
        row = index // ncols
        col = index % ncols
        cell_left = left + col * cell_size_m
        cell_top = top - row * cell_size_m
        cell_right = min(cell_left + cell_size_m, right)
        cell_bottom = max(cell_top - cell_size_m, bottom)
        center_x = (cell_left + cell_right) / 2.0
        center_y = (cell_top + cell_bottom) / 2.0
        lon, lat = transformer.transform(center_x, center_y)
        cells.append(
            OpportunityCell(
                cell_id=_cell_id(index, ncols),
                row=row,
                col=col,
                bounds=(cell_left, cell_bottom, cell_right, cell_top),
                center_lon=float(lon),
                center_lat=float(lat),
                area_m2=float(counts[index] * pixel_area),
                open_ground_m2=float(open_area[index]),
                gap_m2=float(gap_area[index]),
                street_gap_m2=float(street_area[index]),
                interior_open_m2=float(interior_area[index]),
                gap_sites=int(gap_sites[index]),
                street_gap_sites=int(street_sites[index]),
                capacity_small_upper=int(capacity_small[index]),
                capacity_medium_upper=int(capacity_medium[index]),
                capacity_large_upper=int(capacity_large[index]),
                shade_deficit=float(shade[index]),
                equity_score=float(equity[index]),
                priority_class=priority_class[index],
                opportunity_score=float(score[index]),
                opportunity_tier=str(tiers[index]),
            )
        )
    return tuple(cells)


def opportunity_geojson(
    cells: tuple[OpportunityCell, ...],
    *,
    crs: str,
    metadata: Mapping[str, object],
) -> dict[str, object]:
    """Build a WGS84 GeoJSON FeatureCollection from opportunity cells.

    Parameters
    ----------
    cells : tuple of OpportunityCell
        Cells to export.
    crs : str
        Projected CRS of the cell bounds.
    metadata : mapping
        Product metadata copied into the collection.

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
        "name": "planting_opportunity",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "metadata": dict(metadata),
        "features": features,
    }


def write_opportunity_product(
    cells: tuple[OpportunityCell, ...],
    out_dir: Path,
    *,
    crs: str,
    metadata: Mapping[str, object],
    stem: str = "planting_opportunity",
) -> dict[str, Path]:
    """Write JSON, GeoJSON, and PNG products for the opportunity grid.

    Parameters
    ----------
    cells : tuple of OpportunityCell
        Opportunity cells.
    out_dir : Path
        Destination directory.
    crs : str
        Projected CRS of the cell bounds.
    metadata : mapping
        Product metadata, including method and evidence.
    stem : str
        Output file stem.

    Returns
    -------
    dict of str to Path
        Written paths keyed by product name.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "fresh-urban-forest.planting-opportunity.v1",
        "metadata": dict(metadata),
        "cells": [cell.to_dict() for cell in cells],
    }
    json_path = out_dir / f"{stem}.json"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    geojson_path = out_dir / f"{stem}.geojson"
    geojson_path.write_text(
        json.dumps(
            opportunity_geojson(cells, crs=crs, metadata=metadata),
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    png_path = out_dir / f"{stem}.png"
    png_path.write_bytes(opportunity_png(cells))
    return {"json": json_path, "geojson": geojson_path, "png": png_path}


def opportunity_png(cells: tuple[OpportunityCell, ...]) -> bytes:
    """Render opportunity tiers as a transparent PNG.

    Parameters
    ----------
    cells : tuple of OpportunityCell
        Opportunity cells.

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
        rgba[cell.row, cell.col] = TIER_COLOURS.get(cell.opportunity_tier, TIER_COLOURS["none"])
    image = Image.fromarray(rgba, mode="RGBA")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _component_sites(
    mask: NDArray[np.bool_],
    *,
    grid_id: NDArray[np.int64],
    nrows: int,
    ncols: int,
    pixel_area: float,
    min_area_m2: float,
) -> NDArray[np.int64]:
    """Count contiguous components at least a minimum area, by first pixel cell."""
    components, count = label(np.asarray(mask, dtype=np.bool_), structure=np.ones((3, 3)))
    if count == 0:
        return np.zeros(nrows * ncols, dtype=np.int64)
    areas = np.bincount(components.ravel(), minlength=count + 1).astype(np.float64) * pixel_area
    keep = np.zeros(count + 1, dtype=np.bool_)
    keep[1:] = areas[1:] >= min_area_m2
    flat = components.ravel()
    _, first_index = np.unique(flat, return_index=True)
    first_label = flat[first_index]
    valid = keep[first_label]
    first_cell = grid_id.ravel()[first_index[valid]]
    return np.bincount(first_cell, minlength=nrows * ncols).astype(np.int64)


def _cell_id(index: int, ncols: int) -> str:
    """Return the stable row-column cell identifier."""
    return f"r{index // ncols:02d}c{index % ncols:02d}"


def _as_float(value: object) -> float:
    """Convert a JSON value to float, returning NaN when missing."""
    if value is None:
        return float("nan")
    try:
        return float(value)  # type: ignore[arg-type]  # JSON values may be numeric strings.
    except (TypeError, ValueError):
        return float("nan")


__all__ = [
    "DEFAULT_CANOPY_THRESHOLD_M",
    "DEFAULT_GAP_DISTANCE_M",
    "DEFAULT_SITE_MIN_AREA_M2",
    "DEFAULT_SLOPE_MAX_DEG",
    "DEFAULT_STREET_DISTANCE_M",
    "GAP_EVIDENCE",
    "OPPORTUNITY_EVIDENCE",
    "GapMasks",
    "OpportunityCell",
    "build_gap_masks",
    "build_opportunity_grid",
    "opportunity_geojson",
    "opportunity_png",
    "slope_degrees",
    "write_opportunity_product",
]
