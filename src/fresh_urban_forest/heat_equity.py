"""Open land-surface temperature and a heat-equity screen.

The module reads public Landsat Collection 2 Level-2 surface temperature
(``ST_B10``) and quality flags, composites cloud-free summer scenes, and joins
the result to the P38 400 m social-equity cells. The output is a surface-
temperature screening layer. It is not air temperature, pedestrian thermal
comfort, a health outcome model, or a proprietary tree-equity index.
"""

from __future__ import annotations

import io
import json
import math
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import numpy as np
import rasterio
from numpy.typing import NDArray
from PIL import Image
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from shapely.geometry import Polygon, mapping

from fresh_urban_forest.evidence import Evidence, evidence

LST_SCALE = 0.00341802
LST_OFFSET_K = 149.0
LST_INVALID_BELOW_C = -20.0
LST_INVALID_ABOVE_C = 70.0
QA_INVALID_BITS = (1 << 1) | (1 << 2) | (1 << 3) | (1 << 4) | (1 << 5) | (1 << 7)
QA_FILL_BIT = 1

LST_EVIDENCE = evidence(
    "measured",
    "landsat-c2-l2-st-b10",
    uncertainty=(
        "Landsat surface temperature is a 30 m satellite retrieval at the overpass "
        "time, not air temperature or pedestrian thermal comfort. Cloud masking, "
        "mixed pixels, emissivity, and the 30 m footprint remain sources of error."
    ),
    source="USGS/NASA Landsat Collection 2 Level-2, ST_B10 and QA_PIXEL.",
)

HEAT_EQUITY_EVIDENCE = evidence(
    "scenario",
    "lst-plus-p38-census-equity",
    uncertainty=(
        "The heat-equity index gives LST one fifth of the weight and the four P38 "
        "Census indicators the other four fifths. It is a relative screen, not a "
        "validated vulnerability model or a planting plan."
    ),
    source=(
        "P38 social-equity cell score plus public Landsat LST; inspired by the "
        "five-indicator TESPI concept, independently implemented."
    ),
)

TIER_COLOURS: Mapping[str, tuple[int, int, int, int]] = {
    "high": (178, 24, 43, 220),
    "medium": (239, 138, 52, 205),
    "low": (69, 117, 180, 190),
    "none": (0, 0, 0, 0),
}


@dataclass(frozen=True, slots=True)
class LSTScene:
    """One reprojected Landsat surface-temperature scene.

    Attributes
    ----------
    scene_id : str
        Scene or item identifier.
    lst_c : numpy.ndarray
        Surface temperature in degrees Celsius.
    valid : numpy.ndarray
        Cloud-free, non-water, non-building, plausible LST mask.
    bounds : tuple of float
        ``(left, bottom, right, top)``.
    shape : tuple of int
        Grid shape.
    transform : affine.Affine
        Target transform.
    evidence : Evidence
        Method and uncertainty.
    """

    scene_id: str
    lst_c: NDArray[np.float32]
    valid: NDArray[np.bool_]
    bounds: tuple[float, float, float, float]
    shape: tuple[int, int]
    transform: object
    evidence: Evidence

    def to_dict(self) -> dict[str, object]:
        """Convert metadata to a JSON-safe mapping.

        Returns
        -------
        dict
            Scene id, valid-pixel count, and evidence.
        """
        return {
            "scene_id": self.scene_id,
            "valid_pixels": int(np.count_nonzero(self.valid)),
            "shape": list(self.shape),
            "bounds": list(self.bounds),
            "evidence": self.evidence.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class LSTComposite:
    """Median composite of several Landsat scenes.

    Attributes
    ----------
    lst_c : numpy.ndarray
        Median surface temperature in degrees Celsius.
    valid_count : numpy.ndarray
        Number of valid scenes per pixel.
    bounds : tuple of float
        ``(left, bottom, right, top)``.
    shape : tuple of int
        Grid shape.
    transform : object
        Target transform.
    scenes : tuple of LSTScene
        Input scenes.
    evidence : Evidence
        Method and uncertainty.
    """

    lst_c: NDArray[np.float32]
    valid_count: NDArray[np.uint8]
    bounds: tuple[float, float, float, float]
    shape: tuple[int, int]
    transform: object
    scenes: tuple[LSTScene, ...]
    evidence: Evidence

    def to_dict(self) -> dict[str, object]:
        """Convert metadata to a JSON-safe mapping.

        Returns
        -------
        dict
            Scene list, valid-pixel summary, and evidence.
        """
        return {
            "scenes": [scene.to_dict() for scene in self.scenes],
            "valid_pixels": int(np.count_nonzero(np.isfinite(self.lst_c))),
            "bounds": list(self.bounds),
            "shape": list(self.shape),
            "evidence": self.evidence.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class HeatEquityCell:
    """One 400 m heat-equity cell.

    Attributes
    ----------
    cell_id : str
        Stable row-column identifier.
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
    lst_mean_c : float
        Mean valid LST in the cell.
    lst_p90_c : float
        90th-percentile valid LST in the cell.
    lst_valid_pixels : int
        Number of valid 30 m pixels.
    lst_coverage_pct : float
        Valid share of the cell's 30 m pixels.
    heat_percentile : float
        Relative LST percentile, zero to one.
    social_equity_score : float
        P38 social-equity score, zero to one.
    social_equity_percentile : float
        Relative social-equity percentile.
    shade_deficit : float
        P38 shade deficit.
    priority_class : str
        P38 shade-equity class.
    tespi_like : float
        Five-part index: LST plus the four P38 Census indicators.
    heat_equity_tier : str
        ``high``, ``medium``, ``low``, or ``none``.
    """

    cell_id: str
    row: int
    col: int
    bounds: tuple[float, float, float, float]
    center_lon: float
    center_lat: float
    area_m2: float
    lst_mean_c: float
    lst_p90_c: float
    lst_valid_pixels: int
    lst_coverage_pct: float
    heat_percentile: float
    social_equity_score: float
    social_equity_percentile: float
    shade_deficit: float
    priority_class: str
    tespi_like: float
    heat_equity_tier: str

    def to_dict(self) -> dict[str, object]:
        """Convert the cell to a JSON-safe mapping.

        Returns
        -------
        dict
            Cell metrics, percentiles, and tier.
        """
        return {
            "cell_id": self.cell_id,
            "row": self.row,
            "col": self.col,
            "bounds": [round(value, 3) for value in self.bounds],
            "center_lon": round(self.center_lon, 6),
            "center_lat": round(self.center_lat, 6),
            "area_m2": round(self.area_m2, 1),
            "lst_mean_c": round(self.lst_mean_c, 2),
            "lst_p90_c": round(self.lst_p90_c, 2),
            "lst_valid_pixels": self.lst_valid_pixels,
            "lst_coverage_pct": round(self.lst_coverage_pct, 2),
            "heat_percentile": round(self.heat_percentile, 4),
            "social_equity_score": (
                round(self.social_equity_score, 4)
                if math.isfinite(self.social_equity_score)
                else None
            ),
            "social_equity_percentile": (
                round(self.social_equity_percentile, 4)
                if math.isfinite(self.social_equity_percentile)
                else None
            ),
            "shade_deficit": (
                round(self.shade_deficit, 4) if math.isfinite(self.shade_deficit) else None
            ),
            "priority_class": self.priority_class,
            "tespi_like": round(self.tespi_like, 4),
            "heat_equity_tier": self.heat_equity_tier,
        }


def read_landsat_lst(
    st_path: Path,
    qa_path: Path,
    *,
    bounds: tuple[float, float, float, float],
    crs: str,
    resolution_m: float = 30.0,
    exclusion_mask: NDArray[np.bool_] | None = None,
    scene_id: str | None = None,
) -> LSTScene:
    """Read and reproject one Landsat ST_B10 scene.

    Parameters
    ----------
    st_path : Path
        Landsat Collection 2 ``ST_B10`` GeoTIFF.
    qa_path : Path
        Matching ``QA_PIXEL`` GeoTIFF.
    bounds : tuple of float
        Target ``(left, bottom, right, top)`` in the target CRS.
    crs : str
        Target projected CRS.
    resolution_m : float
        Target cell size in metres.
    exclusion_mask : numpy.ndarray or None
        Optional mask of buildings, water, or other excluded pixels.
    scene_id : str or None
        Scene identifier; defaults to the parent directory name.

    Returns
    -------
    LSTScene
        Reprojected temperature and valid mask.

    Raises
    ------
    ValueError
        When bounds are invalid, the exclusion mask shape is wrong, or the
        scene has no usable pixels.
    """
    left, bottom, right, top = bounds
    if right <= left or top <= bottom:
        raise ValueError("bounds must have positive width and height")
    if resolution_m <= 0.0:
        raise ValueError("resolution_m must be positive")
    width = max(1, math.ceil((right - left) / resolution_m))
    height = max(1, math.ceil((top - bottom) / resolution_m))
    transform = from_origin(left, top, resolution_m, resolution_m)
    with (
        rasterio.open(st_path) as source,
        rasterio.open(qa_path) as qa_source,
        WarpedVRT(
            source,
            crs=crs,
            transform=transform,
            width=width,
            height=height,
            resampling=Resampling.bilinear,
            src_nodata=0,
            dst_nodata=0,
        ) as warped,
        WarpedVRT(
            qa_source,
            crs=crs,
            transform=transform,
            width=width,
            height=height,
            resampling=Resampling.nearest,
            src_nodata=None,
            dst_nodata=0,
        ) as qa_warped,
    ):
        digital_number = warped.read(1).astype(np.float64)
        quality = qa_warped.read(1).astype(np.uint32)
    lst_c = digital_number * LST_SCALE + LST_OFFSET_K - 273.15
    valid = (digital_number > 0.0) & (quality & QA_FILL_BIT == 0)
    valid &= (quality & QA_INVALID_BITS) == 0
    valid &= np.isfinite(lst_c)
    valid &= (lst_c >= LST_INVALID_BELOW_C) & (lst_c <= LST_INVALID_ABOVE_C)
    if exclusion_mask is not None:
        exclusion = np.asarray(exclusion_mask, dtype=np.bool_)
        if exclusion.shape != valid.shape:
            raise ValueError("exclusion_mask must match the target grid")
        valid &= ~exclusion
    if not np.any(valid):
        raise ValueError(f"no usable LST pixels in {st_path}")
    return LSTScene(
        scene_id=scene_id or st_path.parent.name,
        lst_c=np.asarray(lst_c, dtype=np.float32),
        valid=np.asarray(valid, dtype=np.bool_),
        bounds=bounds,
        shape=(height, width),
        transform=transform,
        evidence=LST_EVIDENCE,
    )


def composite_lst(scenes: Sequence[LSTScene]) -> LSTComposite:
    """Compute a median surface-temperature composite.

    Parameters
    ----------
    scenes : sequence of LSTScene
        Reprojected scenes with matching grids.

    Returns
    -------
    LSTComposite
        Median temperature and valid-scene count.

    Raises
    ------
    ValueError
        When no scenes are supplied or their grids do not match.
    """
    if not scenes:
        raise ValueError("at least one scene is required")
    shape = scenes[0].shape
    bounds = scenes[0].bounds
    if any(scene.shape != shape or scene.bounds != bounds for scene in scenes):
        raise ValueError("all scenes must share a grid")
    stack = np.stack(
        [np.where(scene.valid, scene.lst_c, np.nan) for scene in scenes],
        axis=0,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        median = np.nanmedian(stack, axis=0)
    valid_count = np.sum(np.isfinite(stack), axis=0).astype(np.uint8)
    return LSTComposite(
        lst_c=np.asarray(median, dtype=np.float32),
        valid_count=valid_count,
        bounds=bounds,
        shape=shape,
        transform=scenes[0].transform,
        scenes=tuple(scenes),
        evidence=LST_EVIDENCE,
    )


def build_heat_equity_grid(
    composite: LSTComposite,
    *,
    crs: str,
    priority: Mapping[str, Mapping[str, object]] | None = None,
    cell_size_m: float = 400.0,
) -> tuple[HeatEquityCell, ...]:
    """Aggregate an LST composite to 400 m heat-equity cells.

    Parameters
    ----------
    composite : LSTComposite
        Surface-temperature composite.
    crs : str
        Projected CRS of the cell bounds.
    priority : mapping or None
        P38 cells keyed by ``cell_id`` with social-equity fields.
    cell_size_m : float
        Analysis cell size.

    Returns
    -------
    tuple of HeatEquityCell
        Cells with at least one valid LST pixel.

    Raises
    ------
    ValueError
        When the cell size is not positive.
    """
    if cell_size_m <= 0.0:
        raise ValueError("cell_size_m must be positive")
    height, width = composite.shape
    left, bottom, right, top = composite.bounds
    ncols = max(1, math.ceil((right - left) / cell_size_m))
    nrows = max(1, math.ceil((top - bottom) / cell_size_m))
    cell_x = (right - left) / width
    cell_y = (top - bottom) / height
    rows, cols = np.indices(composite.shape, dtype=np.float64)
    x = left + (cols + 0.5) * cell_x
    y = top - (rows + 0.5) * cell_y
    grid_x = np.clip(np.floor((x - left) / cell_size_m).astype(np.int64), 0, ncols - 1)
    grid_y = np.clip(np.floor((top - y) / cell_size_m).astype(np.int64), 0, nrows - 1)
    grid_id = grid_y * ncols + grid_x
    valid = np.isfinite(composite.lst_c)
    total_counts = np.bincount(grid_id.ravel(), minlength=nrows * ncols).astype(np.float64)
    valid_counts = np.bincount(grid_id[valid], minlength=nrows * ncols).astype(np.float64)
    lst_sum = np.bincount(
        grid_id[valid],
        weights=composite.lst_c[valid].astype(np.float64),
        minlength=nrows * ncols,
    )
    means = np.divide(
        lst_sum,
        valid_counts,
        out=np.full(nrows * ncols, np.nan),
        where=valid_counts > 0,
    )
    p90 = np.full(nrows * ncols, np.nan, dtype=np.float64)
    for index in range(nrows * ncols):
        if valid_counts[index] == 0:
            continue
        values = composite.lst_c[(grid_id == index) & valid]
        if values.size:
            p90[index] = float(np.percentile(values, 90))
    heat_percentile = _percentile_rank(means)
    social = np.full(nrows * ncols, np.nan, dtype=np.float64)
    shade = np.full(nrows * ncols, np.nan, dtype=np.float64)
    priority_class = ["NA"] * (nrows * ncols)
    if priority:
        for index in range(nrows * ncols):
            priority_row = priority.get(_cell_id(index, ncols))
            if priority_row is None:
                continue
            social[index] = _as_float(priority_row.get("equity_score"))
            shade[index] = _as_float(priority_row.get("shade_deficit"))
            priority_class[index] = str(priority_row.get("priority_class", "NA"))
    social_percentile = _percentile_rank(social)
    tespi = np.where(
        np.isfinite(social_percentile),
        (4.0 * social_percentile + heat_percentile) / 5.0,
        heat_percentile,
    )
    valid_cells = np.isfinite(means)
    tiers = np.full(nrows * ncols, "none", dtype=object)
    if np.any(valid_cells):
        low, high = np.nanquantile(tespi[valid_cells], [1.0 / 3.0, 2.0 / 3.0])
        tiers[valid_cells & (tespi >= high)] = "high"
        tiers[valid_cells & (tespi >= low) & (tespi < high)] = "medium"
        tiers[valid_cells & (tespi < low)] = "low"
    cells: list[HeatEquityCell] = []
    transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    for index in range(nrows * ncols):
        if valid_counts[index] <= 0.0:
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
            HeatEquityCell(
                cell_id=_cell_id(index, ncols),
                row=row,
                col=col,
                bounds=(cell_left, cell_bottom, cell_right, cell_top),
                center_lon=float(lon),
                center_lat=float(lat),
                area_m2=float(total_counts[index] * cell_x * cell_y),
                lst_mean_c=float(means[index]),
                lst_p90_c=float(p90[index]),
                lst_valid_pixels=int(valid_counts[index]),
                lst_coverage_pct=float(100.0 * valid_counts[index] / max(total_counts[index], 1.0)),
                heat_percentile=float(heat_percentile[index]),
                social_equity_score=float(social[index]),
                social_equity_percentile=float(social_percentile[index]),
                shade_deficit=float(shade[index]),
                priority_class=priority_class[index],
                tespi_like=float(tespi[index]),
                heat_equity_tier=str(tiers[index]),
            )
        )
    return tuple(cells)


def heat_equity_geojson(
    cells: tuple[HeatEquityCell, ...],
    *,
    crs: str,
    metadata: Mapping[str, object],
) -> dict[str, object]:
    """Build a WGS84 GeoJSON FeatureCollection from heat-equity cells.

    Parameters
    ----------
    cells : tuple of HeatEquityCell
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
        "name": "heat_equity",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "metadata": dict(metadata),
        "features": features,
    }


def write_heat_equity_product(
    cells: tuple[HeatEquityCell, ...],
    out_dir: Path,
    *,
    crs: str,
    metadata: Mapping[str, object],
    stem: str = "heat_equity",
) -> dict[str, Path]:
    """Write JSON, GeoJSON, and PNG products for the heat-equity grid.

    Parameters
    ----------
    cells : tuple of HeatEquityCell
        Heat-equity cells.
    out_dir : Path
        Destination directory.
    crs : str
        Projected CRS of the cell bounds.
    metadata : mapping
        Product metadata, including methods and evidence.
    stem : str
        Output file stem.

    Returns
    -------
    dict of str to Path
        Written paths keyed by product name.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "fresh-urban-forest.heat-equity.v1",
        "metadata": dict(metadata),
        "cells": [cell.to_dict() for cell in cells],
    }
    json_path = out_dir / f"{stem}.json"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    geojson_path = out_dir / f"{stem}.geojson"
    geojson_path.write_text(
        json.dumps(
            heat_equity_geojson(cells, crs=crs, metadata=metadata),
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    png_path = out_dir / f"{stem}.png"
    png_path.write_bytes(heat_equity_png(cells))
    return {"json": json_path, "geojson": geojson_path, "png": png_path}


def heat_equity_png(cells: tuple[HeatEquityCell, ...]) -> bytes:
    """Render heat-equity tiers as a transparent PNG.

    Parameters
    ----------
    cells : tuple of HeatEquityCell
        Heat-equity cells.

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
        rgba[cell.row, cell.col] = TIER_COLOURS.get(cell.heat_equity_tier, TIER_COLOURS["none"])
    image = Image.fromarray(rgba, mode="RGBA")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _percentile_rank(values: NDArray[np.floating]) -> NDArray[np.float64]:
    """Calculate a percentile rank from zero to one, preserving NaN."""
    array = np.asarray(values, dtype=np.float64)
    result = np.full(array.shape, np.nan, dtype=np.float64)
    valid = np.isfinite(array)
    if not np.any(valid):
        return result
    order = np.argsort(array[valid], kind="stable")
    ranks = np.empty(order.size, dtype=np.float64)
    ranks[order] = np.arange(1, order.size + 1, dtype=np.float64)
    result[valid] = ranks / order.size
    return result


def _cell_id(index: int, ncols: int) -> str:
    """Return the stable row-column cell identifier."""
    return f"r{index // ncols:02d}c{index % ncols:02d}"


def _as_float(value: object) -> float:
    """Convert a JSON value to float, returning NaN when missing."""
    if value is None:
        return float("nan")
    try:
        return float(cast(float, value))
    except (TypeError, ValueError):
        return float("nan")


__all__ = [
    "HEAT_EQUITY_EVIDENCE",
    "LST_EVIDENCE",
    "LST_OFFSET_K",
    "LST_SCALE",
    "HeatEquityCell",
    "LSTComposite",
    "LSTScene",
    "build_heat_equity_grid",
    "composite_lst",
    "heat_equity_geojson",
    "heat_equity_png",
    "read_landsat_lst",
    "write_heat_equity_product",
]
