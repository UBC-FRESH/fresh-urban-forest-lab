"""Raster shade and a CanopyFit-inspired 400 m priority screen.

The published CanopyFit workflow combines a digital surface model, solar
radiation, a 400 m analysis grid, a tree-equity index, and median splits into
eight priority classes. Its code, land-cover product, and municipal constraint
layers are not public. This module reimplements the transferable parts with
open inputs only:

* shade from a public LiDAR canopy surface and building heights;
* a 400 m grid with shade deficit, canopy cover, and shade efficiency; and
* a census-based social-equity screen using open Statistics Canada data.

It does not model planting feasibility, underground utilities, ownership, or
land surface temperature. The output is a screening surface, not a planting
permit.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
from numpy.typing import NDArray
from PIL import Image
from pyproj import Transformer
from rasterio.features import rasterize
from rasterio.transform import from_origin
from scipy.ndimage import map_coordinates
from shapely.geometry import Polygon, mapping

from fresh_urban_forest.evidence import Evidence, evidence
from fresh_urban_forest.models import Building
from fresh_urban_forest.shade import default_step_hours
from fresh_urban_forest.solar import solar_position
from fresh_urban_forest.terrain import project_lonlat, unproject_xy

SHADE_EVIDENCE = evidence(
    "physics",
    "raster-dsm-solar-shadow",
    uncertainty=(
        "The model uses a resampled LiDAR surface as opaque geometry. It ignores leaf "
        "transmissivity, penumbra, facade reflections, and observed weather; shade is a "
        "relative screening surface, not a measured temperature or irradiance."
    ),
    source="Public LiDAR DSM/DEM + NOAA solar position; CanopyFit-inspired, clean-room.",
)

PRIORITY_EVIDENCE = evidence(
    "scenario",
    "median-split-shade-equity-screen",
    uncertainty=(
        "The 400 m classes are relative within the city. Shade deficit is not plantable "
        "area, and the census index is not a heat-vulnerability model."
    ),
    source=(
        "CanopyFit (Nixon et al., 2026, doi:10.1016/j.ufug.2026.129668) for the "
        "classification concept; independent open-data implementation."
    ),
)

PRIORITY_LABELS: Mapping[str, str] = {
    "1A": "high shade deficit, high equity need, high shade efficiency",
    "1B": "high shade deficit, high equity need, low shade efficiency",
    "2A": "high shade deficit, low equity need, high shade efficiency",
    "2B": "high shade deficit, low equity need, low shade efficiency",
    "3A": "low shade deficit, high equity need, high shade efficiency",
    "3B": "low shade deficit, high equity need, low shade efficiency",
    "4A": "low shade deficit, low equity need, high shade efficiency",
    "4B": "low shade deficit, low equity need, low shade efficiency",
    "NA": "not classified",
}

PRIORITY_COLOURS: Mapping[str, tuple[int, int, int, int]] = {
    "1A": (178, 34, 34, 220),
    "1B": (220, 100, 45, 220),
    "2A": (214, 93, 177, 210),
    "2B": (232, 170, 202, 205),
    "3A": (47, 85, 151, 210),
    "3B": (93, 145, 204, 205),
    "4A": (98, 98, 98, 180),
    "4B": (170, 170, 170, 160),
    "NA": (0, 0, 0, 0),
}


@dataclass(frozen=True, slots=True)
class RasterShade:
    """Shade fractions on a regular projected grid.

    Attributes
    ----------
    whens : tuple of datetime.datetime
        Solar samples used in the calculation.
    step_hours : float
        Hours represented by each sample.
    target_height_m : float
        Pedestrian target height above ground.
    tree_shade_fraction : numpy.ndarray
        Fraction of sampled daylight shaded by tree canopy.
    building_shade_fraction : numpy.ndarray
        Fraction of sampled daylight shaded by buildings.
    combined_shade_fraction : numpy.ndarray
        Fraction shaded by trees or buildings.
    sunlit_fraction : numpy.ndarray
        Fraction not shaded by either source.
    metrics : dict
        City-wide means and sample metadata.
    evidence : Evidence
        Method and uncertainty.
    """

    whens: tuple[dt.datetime, ...]
    step_hours: float
    target_height_m: float
    tree_shade_fraction: NDArray[np.float32]
    building_shade_fraction: NDArray[np.float32]
    combined_shade_fraction: NDArray[np.float32]
    sunlit_fraction: NDArray[np.float32]
    metrics: dict[str, float]
    evidence: Evidence

    def to_dict(self) -> dict[str, object]:
        """Convert the non-array metadata to a JSON-safe mapping.

        Returns
        -------
        dict
            Sample times, metrics, and evidence.
        """
        return {
            "whens": [when.isoformat() for when in self.whens],
            "step_hours": self.step_hours,
            "target_height_m": self.target_height_m,
            "metrics": self.metrics,
            "evidence": self.evidence.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class PriorityCell:
    """One 400 m screening cell.

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
    population : float
        Census population estimate in the cell.
    canopy_cover_pct : float
        Share of cell area with canopy at least two metres tall.
    mean_canopy_height_m : float
        Mean canopy height over canopy pixels.
    shade_fraction : float
        Mean combined shade fraction.
    tree_shade_fraction : float
        Mean tree shade fraction.
    building_shade_fraction : float
        Mean building shade fraction.
    shade_deficit : float
        ``1 - shade_fraction``; a screening proxy for unshaded ground.
    shade_efficiency_m2h_per_m3 : float
        Tree-shade area-hours per cubic metre of canopy.
    equity_score : float
        Relative social-equity need, zero to one.
    priority_class : str
        One of ``1A`` to ``4B``, or ``NA``.
    priority_label : str
        Human-readable class description.
    """

    cell_id: str
    row: int
    col: int
    bounds: tuple[float, float, float, float]
    center_lon: float
    center_lat: float
    area_m2: float
    population: float
    canopy_cover_pct: float
    mean_canopy_height_m: float
    shade_fraction: float
    tree_shade_fraction: float
    building_shade_fraction: float
    shade_deficit: float
    shade_efficiency_m2h_per_m3: float
    equity_score: float
    priority_class: str
    priority_label: str

    def to_dict(self) -> dict[str, object]:
        """Convert the cell to a JSON-safe mapping.

        Returns
        -------
        dict
            Cell identifiers, metrics, and class.
        """
        return {
            "cell_id": self.cell_id,
            "row": self.row,
            "col": self.col,
            "bounds": [round(value, 3) for value in self.bounds],
            "center_lon": round(self.center_lon, 6),
            "center_lat": round(self.center_lat, 6),
            "area_m2": round(self.area_m2, 1),
            "population": round(self.population, 1),
            "canopy_cover_pct": round(self.canopy_cover_pct, 2),
            "mean_canopy_height_m": round(self.mean_canopy_height_m, 2),
            "shade_fraction": round(self.shade_fraction, 4),
            "tree_shade_fraction": round(self.tree_shade_fraction, 4),
            "building_shade_fraction": round(self.building_shade_fraction, 4),
            "shade_deficit": round(self.shade_deficit, 4),
            "shade_efficiency_m2h_per_m3": round(self.shade_efficiency_m2h_per_m3, 5),
            "equity_score": (
                round(self.equity_score, 4) if math.isfinite(self.equity_score) else None
            ),
            "priority_class": self.priority_class,
            "priority_label": self.priority_label,
        }


def raster_shade(
    *,
    dem: NDArray[np.floating],
    canopy_height: NDArray[np.floating],
    building_height: NDArray[np.floating],
    bounds: tuple[float, float, float, float],
    crs: str,
    whens: tuple[dt.datetime, ...],
    target_height_m: float = 1.5,
    max_distance_m: float = 200.0,
    step_m: float = 5.0,
) -> RasterShade:
    """Calculate raster shade from a ground, canopy, and building surface.

    The ray-march samples the canopy and building tops toward the sun. A cell
    is shaded when a sampled surface rises above the pedestrian target plus the
    solar elevation over that distance.

    Parameters
    ----------
    dem : numpy.ndarray
        Ground elevation, shape ``(height, width)``.
    canopy_height : numpy.ndarray
        Canopy height above ground, same shape as ``dem``.
    building_height : numpy.ndarray
        Building height above ground, same shape as ``dem``.
    bounds : tuple of float
        ``(left, bottom, right, top)`` in the projected CRS.
    crs : str
        Projected CRS.
    whens : tuple of datetime.datetime
        Solar samples.
    target_height_m : float
        Pedestrian target height above ground.
    max_distance_m : float
        Maximum ray length.
    step_m : float
        Ray sample spacing.

    Returns
    -------
    RasterShade
        Shade fractions and metadata.

    Raises
    ------
    ValueError
        When the arrays have different shapes, the bounds are invalid, or the
        sampling parameters are not positive.
    """
    dem_array = np.asarray(dem, dtype=np.float64)
    canopy_array = np.asarray(canopy_height, dtype=np.float64)
    building_array = np.asarray(building_height, dtype=np.float64)
    if not (dem_array.shape == canopy_array.shape == building_array.shape and dem_array.ndim == 2):
        raise ValueError("dem, canopy_height, and building_height must share a 2-D shape")
    left, bottom, right, top = bounds
    if right <= left or top <= bottom:
        raise ValueError("bounds must have positive width and height")
    if target_height_m <= 0.0 or max_distance_m <= 0.0 or step_m <= 0.0:
        raise ValueError("target height, ray length, and step must be positive")
    if not whens:
        raise ValueError("at least one solar sample is required")

    height, width = dem_array.shape
    cell_x = (right - left) / width
    cell_y = (top - bottom) / height
    center_lon, center_lat = unproject_xy(
        (left + right) / 2.0,
        (bottom + top) / 2.0,
        crs,
    )
    ground = np.nan_to_num(dem_array, nan=0.0)
    canopy = np.clip(np.nan_to_num(canopy_array, nan=0.0), 0.0, None)
    building = np.clip(np.nan_to_num(building_array, nan=0.0), 0.0, None)
    tree_top = ground + canopy
    building_top = ground + building
    target = ground + target_height_m
    ordered_whens = tuple(sorted(whens))
    step_hours = default_step_hours(ordered_whens)
    rows, cols = np.indices((height, width), dtype=np.float64)
    tree_hours = np.zeros((height, width), dtype=np.float64)
    building_hours = np.zeros((height, width), dtype=np.float64)
    combined_hours = np.zeros((height, width), dtype=np.float64)
    sample_count = 0
    for when in ordered_whens:
        sun = solar_position(when, center_lon, center_lat)
        if not sun.is_daylight:
            continue
        sample_count += 1
        direction_x = math.sin(math.radians(sun.azimuth_deg))
        direction_y = math.cos(math.radians(sun.azimuth_deg))
        tan_altitude = math.tan(math.radians(max(sun.altitude_deg, 1.0)))
        tree_mask = np.zeros((height, width), dtype=np.bool_)
        building_mask = np.zeros((height, width), dtype=np.bool_)
        for distance in np.arange(step_m, max_distance_m + step_m * 0.5, step_m):
            sample_rows = rows - direction_y * distance / cell_y
            sample_cols = cols + direction_x * distance / cell_x
            inside = (
                (sample_rows >= 0.0)
                & (sample_rows < height - 1)
                & (sample_cols >= 0.0)
                & (sample_cols < width - 1)
            )
            sampled_tree = map_coordinates(
                tree_top,
                [sample_rows, sample_cols],
                order=1,
                mode="constant",
                cval=-1e9,
            )
            sampled_building = map_coordinates(
                building_top,
                [sample_rows, sample_cols],
                order=1,
                mode="constant",
                cval=-1e9,
            )
            threshold = target + distance * tan_altitude
            tree_mask |= inside & (sampled_tree > threshold)
            building_mask |= inside & (sampled_building > threshold)
        combined_mask = tree_mask | building_mask
        tree_hours += tree_mask.astype(np.float64) * step_hours
        building_hours += building_mask.astype(np.float64) * step_hours
        combined_hours += combined_mask.astype(np.float64) * step_hours
    if sample_count == 0:
        raise ValueError("no daylight samples were supplied")
    daylight_hours = sample_count * step_hours
    tree_fraction = (tree_hours / daylight_hours).astype(np.float32)
    building_fraction = (building_hours / daylight_hours).astype(np.float32)
    combined_fraction = (combined_hours / daylight_hours).astype(np.float32)
    sunlit_fraction = (1.0 - combined_fraction).astype(np.float32)
    metrics = {
        "tree_shade_fraction": float(np.mean(tree_fraction, dtype=np.float64)),
        "building_shade_fraction": float(np.mean(building_fraction, dtype=np.float64)),
        "combined_shade_fraction": float(np.mean(combined_fraction, dtype=np.float64)),
        "sunlit_fraction": float(np.mean(sunlit_fraction, dtype=np.float64)),
        "daylight_samples": float(sample_count),
        "daylight_sampled_hours": float(daylight_hours),
    }
    return RasterShade(
        whens=tuple(sorted(whens)),
        step_hours=step_hours,
        target_height_m=target_height_m,
        tree_shade_fraction=tree_fraction,
        building_shade_fraction=building_fraction,
        combined_shade_fraction=combined_fraction,
        sunlit_fraction=sunlit_fraction,
        metrics=metrics,
        evidence=SHADE_EVIDENCE,
    )


def building_height_raster(
    buildings: tuple[Building, ...],
    *,
    bounds: tuple[float, float, float, float],
    shape: tuple[int, int],
    crs: str,
) -> NDArray[np.float32]:
    """Rasterise building heights onto a regular grid.

    Parameters
    ----------
    buildings : tuple of Building
        Building footprints with WGS84 rings and heights.
    bounds : tuple of float
        ``(left, bottom, right, top)`` in the projected CRS.
    shape : tuple of int
        ``(height, width)`` output shape.
    crs : str
        Projected CRS.

    Returns
    -------
    numpy.ndarray
        Building height above ground, with zero where no building is present.
    """
    height, width = shape
    left, bottom, right, top = bounds
    transform = from_origin(left, top, (right - left) / width, (top - bottom) / height)
    shapes: list[tuple[Polygon, float]] = []
    for building in buildings:
        if not building.rings:
            continue
        ring = building.rings[0]
        points = [project_lonlat(lon, lat, crs) for lon, lat in ring]
        if len(points) < 3:
            continue
        polygon = Polygon(points)
        if polygon.is_empty:
            continue
        shapes.append((polygon, max(float(building.height_m), 0.0)))
    if not shapes:
        return np.zeros(shape, dtype=np.float32)
    return np.asarray(
        rasterize(
            shapes,
            out_shape=shape,
            transform=transform,
            fill=0.0,
            dtype="float32",
        ),
        dtype=np.float32,
    )


def build_priority_grid(
    shade: RasterShade,
    *,
    bounds: tuple[float, float, float, float],
    crs: str,
    canopy_height: NDArray[np.floating],
    building_mask: NDArray[np.bool_] | None = None,
    water_mask: NDArray[np.bool_] | None = None,
    equity: gpd.GeoDataFrame | None = None,
    cell_size_m: float = 400.0,
    canopy_threshold_m: float = 2.0,
) -> tuple[PriorityCell, ...]:
    """Aggregate shade, canopy, and equity into 400 m screening cells.

    Parameters
    ----------
    shade : RasterShade
        Output of :func:`raster_shade`.
    bounds : tuple of float
        ``(left, bottom, right, top)`` in the projected CRS.
    crs : str
        Projected CRS.
    canopy_height : numpy.ndarray
        Canopy height above ground, same shape as the shade arrays.
    building_mask : numpy.ndarray or None
        Optional building mask excluded from canopy cover.
    water_mask : numpy.ndarray or None
        Optional water mask excluded from canopy cover.
    equity : geopandas.GeoDataFrame or None
        Dissemination-area polygons with ``population`` and ``equity_score``.
    cell_size_m : float
        Analysis grid size.
    canopy_threshold_m : float
        Minimum canopy height counted as cover.

    Returns
    -------
    tuple of PriorityCell
        Cells with at least one raster pixel, ordered by row and column.

    Raises
    ------
    ValueError
        When the canopy shape differs from the shade shape or the cell size is
        not positive.
    """
    canopy = np.asarray(canopy_height, dtype=np.float64)
    shape = shade.combined_shade_fraction.shape
    if canopy.shape != shape:
        raise ValueError("canopy_height must match the shade array shape")
    if cell_size_m <= 0.0:
        raise ValueError("cell_size_m must be positive")
    left, bottom, right, top = bounds
    height, width = shape
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

    def _sum(values: NDArray[np.floating]) -> NDArray[np.float64]:
        return np.bincount(
            grid_id.ravel(),
            weights=np.asarray(values, dtype=np.float64).ravel(),
            minlength=nrows * ncols,
        )

    shade_sum = _sum(shade.combined_shade_fraction)
    tree_sum = _sum(shade.tree_shade_fraction)
    building_sum = _sum(shade.building_shade_fraction)
    shade_fraction = np.divide(shade_sum, counts, out=np.zeros_like(counts), where=counts > 0)
    tree_shade_fraction = np.divide(tree_sum, counts, out=np.zeros_like(counts), where=counts > 0)
    building_shade_fraction = np.divide(
        building_sum, counts, out=np.zeros_like(counts), where=counts > 0
    )

    canopy_mask = np.isfinite(canopy) & (canopy >= canopy_threshold_m)
    if building_mask is not None:
        canopy_mask &= ~np.asarray(building_mask, dtype=np.bool_)
    if water_mask is not None:
        canopy_mask &= ~np.asarray(water_mask, dtype=np.bool_)
    canopy_count = _sum(canopy_mask.astype(np.float64))
    canopy_pct = np.divide(
        canopy_count * 100.0, counts, out=np.zeros_like(counts), where=counts > 0
    )
    canopy_volume = _sum(np.where(canopy_mask, canopy, 0.0)) * pixel_area
    canopy_height_sum = _sum(np.where(canopy_mask, canopy, 0.0))
    mean_canopy_height = np.divide(
        canopy_height_sum,
        canopy_count,
        out=np.zeros_like(counts),
        where=canopy_count > 0,
    )
    tree_shade_area_hours = tree_sum * pixel_area
    efficiency = np.divide(
        tree_shade_area_hours,
        canopy_volume,
        out=np.zeros_like(counts),
        where=canopy_volume > 0,
    )

    population = np.zeros(nrows * ncols, dtype=np.float64)
    equity_score = np.full(nrows * ncols, np.nan, dtype=np.float64)
    if equity is not None:
        population, equity_score = _equity_by_cell(
            equity,
            bounds=bounds,
            shape=shape,
            crs=crs,
            grid_id=grid_id,
            nrows=nrows,
            ncols=ncols,
        )

    equity_valid = (counts > 0) & np.isfinite(shade_fraction) & np.isfinite(equity_score)
    median_deficit = (
        float(np.median(1.0 - shade_fraction[equity_valid])) if np.any(equity_valid) else 0.0
    )
    median_equity = float(np.median(equity_score[equity_valid])) if np.any(equity_valid) else 0.0
    median_efficiency = float(np.median(efficiency[equity_valid])) if np.any(equity_valid) else 0.0
    deficit = 1.0 - shade_fraction
    classes: list[str] = []
    for index in range(nrows * ncols):
        if not equity_valid[index]:
            classes.append("NA")
            continue
        collapsed = (
            1
            if deficit[index] >= median_deficit and equity_score[index] >= median_equity
            else 2
            if deficit[index] >= median_deficit
            else 3
            if equity_score[index] >= median_equity
            else 4
        )
        suffix = "A" if efficiency[index] >= median_efficiency else "B"
        classes.append(f"{collapsed}{suffix}")

    cells: list[PriorityCell] = []
    transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    for index in range(nrows * ncols):
        if counts[index] <= 0.0:
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
        priority_class = classes[index]
        cells.append(
            PriorityCell(
                cell_id=f"r{row:02d}c{col:02d}",
                row=row,
                col=col,
                bounds=(cell_left, cell_bottom, cell_right, cell_top),
                center_lon=float(lon),
                center_lat=float(lat),
                area_m2=float(counts[index] * pixel_area),
                population=float(population[index]),
                canopy_cover_pct=float(canopy_pct[index]),
                mean_canopy_height_m=float(mean_canopy_height[index]),
                shade_fraction=float(shade_fraction[index]),
                tree_shade_fraction=float(tree_shade_fraction[index]),
                building_shade_fraction=float(building_shade_fraction[index]),
                shade_deficit=float(deficit[index]),
                shade_efficiency_m2h_per_m3=float(efficiency[index]),
                equity_score=float(equity_score[index]),
                priority_class=priority_class,
                priority_label=PRIORITY_LABELS[priority_class],
            )
        )
    return tuple(cells)


def priority_geojson(
    cells: tuple[PriorityCell, ...],
    *,
    crs: str,
    metadata: Mapping[str, object],
) -> dict[str, object]:
    """Build a WGS84 GeoJSON FeatureCollection from priority cells.

    Parameters
    ----------
    cells : tuple of PriorityCell
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
        polygon = Polygon(corners)
        features.append(
            {
                "type": "Feature",
                "id": cell.cell_id,
                "geometry": mapping(polygon),
                "properties": cell.to_dict(),
            }
        )
    return {
        "type": "FeatureCollection",
        "name": "shade_equity_priority",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "metadata": dict(metadata),
        "features": features,
    }


def write_priority_product(
    cells: tuple[PriorityCell, ...],
    out_dir: Path,
    *,
    crs: str,
    metadata: Mapping[str, object],
    stem: str = "heat_priority",
) -> dict[str, Path]:
    """Write JSON, GeoJSON, and PNG products for a priority grid.

    Parameters
    ----------
    cells : tuple of PriorityCell
        Priority cells.
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
        "schema_version": "fresh-urban-forest.heat-priority.v1",
        "metadata": dict(metadata),
        "cells": [cell.to_dict() for cell in cells],
    }
    json_path = out_dir / f"{stem}.json"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    geojson_path = out_dir / f"{stem}.geojson"
    geojson_path.write_text(
        json.dumps(
            priority_geojson(cells, crs=crs, metadata=metadata),
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    png_path = out_dir / f"{stem}.png"
    png_path.write_bytes(priority_png(cells))
    return {"json": json_path, "geojson": geojson_path, "png": png_path}


def priority_png(cells: tuple[PriorityCell, ...]) -> bytes:
    """Render a class-coloured 400 m grid as a transparent PNG.

    Parameters
    ----------
    cells : tuple of PriorityCell
        Priority cells.

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
        rgba[cell.row, cell.col] = PRIORITY_COLOURS[cell.priority_class]
    image = Image.fromarray(rgba, mode="RGBA")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _equity_by_cell(
    equity: gpd.GeoDataFrame,
    *,
    bounds: tuple[float, float, float, float],
    shape: tuple[int, int],
    crs: str,
    grid_id: NDArray[np.int64],
    nrows: int,
    ncols: int,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Calculate population-weighted equity values for each analysis cell."""
    frame = equity.to_crs(crs)
    if "equity_score" not in frame.columns:
        raise ValueError("equity frame has no equity_score column")
    population_values = (
        frame["population"].fillna(0.0).to_numpy(dtype=np.float64)
        if "population" in frame.columns
        else np.zeros(len(frame), dtype=np.float64)
    )
    score_values = frame["equity_score"].to_numpy(dtype=np.float64)
    left, bottom, right, top = bounds
    height, width = shape
    transform = from_origin(left, top, (right - left) / width, (top - bottom) / height)
    da_ids = rasterize(
        [(geometry, index + 1) for index, geometry in enumerate(frame.geometry)],
        out_shape=shape,
        transform=transform,
        fill=0,
        dtype="int32",
    ).astype(np.int64)
    pixel_count = np.bincount(da_ids.ravel(), minlength=len(frame) + 1).astype(np.float64)
    pop_by_pixel = np.zeros_like(pixel_count)
    nonzero = pixel_count[1:] > 0
    pop_by_pixel[1:][nonzero] = population_values[nonzero] / pixel_count[1:][nonzero]
    flat_ids = da_ids.ravel()
    pop_pixel = pop_by_pixel[flat_ids]
    score_pixel = np.full(flat_ids.shape, np.nan, dtype=np.float64)
    inside = flat_ids > 0
    score_pixel[inside] = score_values[flat_ids[inside] - 1]
    population = np.bincount(grid_id.ravel(), weights=pop_pixel, minlength=nrows * ncols)
    weighted = np.bincount(
        grid_id.ravel(),
        weights=np.where(np.isfinite(score_pixel), pop_pixel * score_pixel, 0.0),
        minlength=nrows * ncols,
    )
    weight_sum = np.bincount(
        grid_id.ravel(),
        weights=np.where(np.isfinite(score_pixel), pop_pixel, 0.0),
        minlength=nrows * ncols,
    )
    score = np.divide(
        weighted,
        weight_sum,
        out=np.full_like(weighted, np.nan),
        where=weight_sum > 0,
    )
    return population, score


__all__ = [
    "PRIORITY_COLOURS",
    "PRIORITY_EVIDENCE",
    "PRIORITY_LABELS",
    "SHADE_EVIDENCE",
    "PriorityCell",
    "RasterShade",
    "build_priority_grid",
    "building_height_raster",
    "priority_geojson",
    "priority_png",
    "raster_shade",
    "write_priority_product",
]
