"""City-wide and local-area canopy and ecosystem-service metrics.

The calculations are deliberately transparent. Canopy cover and height-field volume come
from the 1 m CHM. Carbon and annual sequestration come from the public inventory and the
generic allometry. Rainfall interception is a screening range, not a measured flux.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import geopandas as gpd
import numpy as np
import rasterio
from numpy.typing import NDArray
from rasterio.features import rasterize
from shapely.geometry import Point

from fresh_urban_forest.allometry import grow_tree, tree_carbon_kg, tree_crown_volume_m3
from fresh_urban_forest.metrics import shannon_index
from fresh_urban_forest.models import TreeRecord
from fresh_urban_forest.terrain import read_raster

CANOPY_THRESHOLD_M = 2.0
ANNUAL_PRECIPITATION_M = 1.0988
INTERCEPTION_FRACTION_LOW = 0.10
INTERCEPTION_FRACTION_HIGH = 0.20


@dataclass(frozen=True, slots=True)
class AreaSummary:
    """Metrics for one local area.

    Attributes
    ----------
    name : str
        Local-area name.
    area_ha : float
        Area in hectares.
    tree_count : int
        Public trees assigned to the area.
    canopy_cover_pct : float
        CHM canopy cover, percent.
    canopy_volume_m3 : float
        Height-field canopy volume.
    tree_crown_volume_m3 : float
        Inventory ellipsoid crown volume.
    carbon_kg : float
        Above-ground carbon storage.
    annual_sequestration_kg : float
        One-year growth-model increment.
    shannon_index : float
        Species diversity.
    native_fraction : float
        Share of native trees.
    tree_height_p50_m : float
        Median inventory height.
    tree_height_p95_m : float
        95th percentile inventory height.
    rainfall_interception_m3_low : float
        Low screening estimate.
    rainfall_interception_m3_high : float
        High screening estimate.
    """

    name: str
    area_ha: float
    tree_count: int
    canopy_cover_pct: float
    canopy_volume_m3: float
    tree_crown_volume_m3: float
    carbon_kg: float
    annual_sequestration_kg: float
    shannon_index: float
    native_fraction: float
    tree_height_p50_m: float
    tree_height_p95_m: float
    rainfall_interception_m3_low: float
    rainfall_interception_m3_high: float

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe mapping.

        Returns
        -------
        dict
            Metric values with units in the keys.
        """
        return {
            "name": self.name,
            "area_ha": round(self.area_ha, 3),
            "tree_count": self.tree_count,
            "canopy_cover_pct": round(self.canopy_cover_pct, 3),
            "canopy_volume_m3": round(self.canopy_volume_m3, 3),
            "tree_crown_volume_m3": round(self.tree_crown_volume_m3, 3),
            "carbon_kg": round(self.carbon_kg, 3),
            "annual_sequestration_kg": round(self.annual_sequestration_kg, 3),
            "shannon_index": round(self.shannon_index, 4),
            "native_fraction": round(self.native_fraction, 4),
            "tree_height_p50_m": round(self.tree_height_p50_m, 3),
            "tree_height_p95_m": round(self.tree_height_p95_m, 3),
            "rainfall_interception_m3_low": round(self.rainfall_interception_m3_low, 3),
            "rainfall_interception_m3_high": round(self.rainfall_interception_m3_high, 3),
        }


def compute_city_metrics(
    trees: tuple[TreeRecord, ...],
    *,
    chm_path: Path,
    building_mask_path: Path,
    water_mask_path: Path,
    aoi_path: Path,
    out_dir: Path,
    aoi_crs: str | None = None,
) -> dict[str, object]:
    """Calculate city and local-area metrics.

    Parameters
    ----------
    trees : tuple of TreeRecord
        Enriched public trees.
    chm_path : Path
        City 1 m CHM.
    building_mask_path : Path
        Building mask.
    water_mask_path : Path
        Water mask.
    aoi_path : Path
        Local-area polygons.
    out_dir : Path
        Output directory.
    aoi_crs : str or None
        CRS for an AOI file with no CRS metadata.

    Returns
    -------
    dict
        JSON-safe city metrics, local-area metrics, methods, and caveats.
    """
    chm = read_raster(chm_path)
    building = _read_mask(building_mask_path, chm.array.shape)
    water = _read_mask(water_mask_path, chm.array.shape)
    areas = gpd.read_file(aoi_path)
    if aoi_crs is not None:
        areas = areas.set_crs(aoi_crs, allow_override=True)
    areas = areas.to_crs(chm.crs)
    area_names = [str(value) for value in areas["name"]]
    area_ids = rasterize(
        [(geom, index + 1) for index, geom in enumerate(areas.geometry)],
        out_shape=chm.array.shape,
        transform=chm.transform,
        fill=0,
        dtype="int16",
    )
    area_pixels = np.bincount(area_ids.ravel(), minlength=len(areas) + 1)
    canopy = np.isfinite(chm.array) & (chm.array >= CANOPY_THRESHOLD_M) & ~building & ~water
    canopy &= area_ids > 0
    canopy_count = np.bincount(area_ids[canopy], minlength=len(areas) + 1)
    volume = np.bincount(
        area_ids[canopy],
        weights=chm.array[canopy].astype(np.float64),
        minlength=len(areas) + 1,
    )
    cell_area = chm.cell_area_m2
    tree_area = _assign_tree_areas(trees, areas, chm.crs)
    tree_groups: dict[int, list[TreeRecord]] = {}
    for tree, area_index in zip(trees, tree_area, strict=True):
        if area_index > 0:
            tree_groups.setdefault(area_index, []).append(tree)
    local: list[AreaSummary] = []
    for index, name in enumerate(area_names, start=1):
        area_ha = area_pixels[index] * cell_area / 10_000.0
        cover_pct = (
            100.0 * canopy_count[index] * cell_area / max(area_pixels[index] * cell_area, 1.0)
        )
        canopy_volume = volume[index] * cell_area
        group = tree_groups.get(index, [])
        tree_values = _tree_values(group)
        local.append(
            AreaSummary(
                name=name,
                area_ha=area_ha,
                tree_count=len(group),
                canopy_cover_pct=cover_pct,
                canopy_volume_m3=canopy_volume,
                tree_crown_volume_m3=tree_values["crown_volume_m3"],
                carbon_kg=tree_values["carbon_kg"],
                annual_sequestration_kg=tree_values["annual_sequestration_kg"],
                shannon_index=tree_values["shannon_index"],
                native_fraction=tree_values["native_fraction"],
                tree_height_p50_m=tree_values["height_p50_m"],
                tree_height_p95_m=tree_values["height_p95_m"],
                rainfall_interception_m3_low=canopy_count[index]
                * cell_area
                * ANNUAL_PRECIPITATION_M
                * INTERCEPTION_FRACTION_LOW,
                rainfall_interception_m3_high=canopy_count[index]
                * cell_area
                * ANNUAL_PRECIPITATION_M
                * INTERCEPTION_FRACTION_HIGH,
            )
        )
    all_values = _tree_values(list(trees))
    total_area_ha = float(area_pixels[1:].sum() * cell_area / 10_000.0)
    total_canopy_area = int(canopy_count[1:].sum()) * cell_area
    city = AreaSummary(
        name="City of Vancouver",
        area_ha=total_area_ha,
        tree_count=len(trees),
        canopy_cover_pct=(
            100.0 * canopy_count[1:].sum() * cell_area / max(total_area_ha * 10_000.0, 1.0)
        ),
        canopy_volume_m3=float(volume[1:].sum() * cell_area),
        tree_crown_volume_m3=all_values["crown_volume_m3"],
        carbon_kg=all_values["carbon_kg"],
        annual_sequestration_kg=all_values["annual_sequestration_kg"],
        shannon_index=all_values["shannon_index"],
        native_fraction=all_values["native_fraction"],
        tree_height_p50_m=all_values["height_p50_m"],
        tree_height_p95_m=all_values["height_p95_m"],
        rainfall_interception_m3_low=total_canopy_area
        * ANNUAL_PRECIPITATION_M
        * INTERCEPTION_FRACTION_LOW,
        rainfall_interception_m3_high=total_canopy_area
        * ANNUAL_PRECIPITATION_M
        * INTERCEPTION_FRACTION_HIGH,
    )
    payload: dict[str, object] = {
        "schema_version": "fresh-urban-forest.city-metrics.v1",
        "city": city.to_dict(),
        "local_areas": [item.to_dict() for item in local],
        "tree_count_total": len(trees),
        "tree_count_assigned": int(sum(1 for value in tree_area if value > 0)),
        "methods": _methods(),
        "caveats": [
            "Canopy cover and height-field volume come from the 2022 leaf-on CHM.",
            "Carbon and annual sequestration use generic species-group allometry, not "
            "local calibration.",
            "Rainfall interception is a 10-20% screening range, not a measured flux.",
            "Public trees exclude private trees; LiDAR includes private canopy.",
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "city_metrics.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    return payload


def _assign_tree_areas(
    trees: tuple[TreeRecord, ...],
    areas: gpd.GeoDataFrame,
    crs: str,
) -> list[int]:
    """Assign each tree to a local-area polygon.

    Parameters
    ----------
    trees : tuple of TreeRecord
        Enriched trees.
    areas : geopandas.GeoDataFrame
        Local areas with a ``name`` column.
    crs : str
        Projected CRS.

    Returns
    -------
    list of int
        Area index, or zero when the tree is outside all local areas.
    """
    points = gpd.GeoDataFrame(
        {"tree_index": np.arange(len(trees), dtype=np.int64)},
        geometry=[
            Point(tree.x_m, tree.y_m)
            for tree in trees
            if tree.x_m is not None and tree.y_m is not None
        ],
        crs=crs,
    )
    if points.empty:
        return [0] * len(trees)
    area_frame = areas[["name", "geometry"]].copy()
    area_frame["area_id"] = np.arange(len(areas), dtype=np.int64) + 1
    joined = gpd.sjoin(points, area_frame[["area_id", "geometry"]], how="left", predicate="within")
    result = [0] * len(trees)
    for _, row in joined.iterrows():
        index = int(cast(int, row["tree_index"]))
        area = row["area_id"]
        result[index] = 0 if area is None or not np.isfinite(area) else int(area)
    return result


def _tree_values(trees: list[TreeRecord]) -> dict[str, float]:
    """Calculate tree-level metrics for a group.

    Parameters
    ----------
    trees : list of TreeRecord
        Tree group.

    Returns
    -------
    dict
        Carbon, sequestration, diversity, native share, and height statistics.
    """
    valid = [
        tree
        for tree in trees
        if tree.dbh_cm is not None
        and tree.dbh_cm > 0
        and str(tree.attributes.get("dbh_outlier", "")).lower() != "true"
    ]
    carbon = sum(tree_carbon_kg(tree) for tree in valid)
    sequestration = 0.0
    for tree in valid:
        grown = grow_tree(tree, 1)
        sequestration += max(0.0, tree_carbon_kg(grown) - tree_carbon_kg(tree))
    species = Counter(tree.species or tree.common_name or "Unknown" for tree in trees)
    heights = [
        float(tree.height_m) for tree in trees if tree.height_m is not None and tree.height_m > 0.5
    ]
    return {
        "crown_volume_m3": sum(tree_crown_volume_m3(tree) for tree in valid),
        "carbon_kg": carbon,
        "annual_sequestration_kg": sequestration,
        "shannon_index": shannon_index(species),
        "native_fraction": sum(1 for tree in trees if tree.native) / max(1, len(trees)),
        "height_p50_m": float(np.median(heights)) if heights else 0.0,
        "height_p95_m": float(np.percentile(heights, 95)) if heights else 0.0,
    }


def _read_mask(path: Path, shape: tuple[int, int]) -> NDArray[np.bool_]:
    """Read a single-band mask and validate its shape."""
    with rasterio.open(path) as dataset:
        array = dataset.read(1).astype(bool)
    if array.shape != shape:
        raise ValueError(f"mask shape {array.shape} does not match CHM shape {shape}")
    return np.asarray(array, dtype=np.bool_)


def _methods() -> Mapping[str, Mapping[str, str]]:
    """Return method and evidence labels for every metric family."""
    return {
        "canopy_cover_pct": {
            "method": "CHM >= 2 m, excluding buildings and water, divided by local-area area",
            "tier": "measured",
        },
        "canopy_volume_m3": {
            "method": "sum of CHM above 2 m multiplied by 1 m² cell area",
            "tier": "measured",
        },
        "tree_crown_volume_m3": {
            "method": "ellipsoid crown volume from inventory height and crown width",
            "tier": "modelled",
        },
        "carbon_kg": {
            "method": "Jenkins et al. (2003) allometry from DBH and species group",
            "tier": "modelled",
        },
        "annual_sequestration_kg": {
            "method": "one-year growth projection minus current carbon",
            "tier": "scenario",
        },
        "rainfall_interception_m3": {
            "method": "canopy area x 1,098.8 mm/yr x 10-20% interception range",
            "tier": "screening",
        },
        "shannon_index": {
            "method": "Shannon diversity of public-tree species labels",
            "tier": "measured",
        },
    }
