"""Full-city inventory loading, enrichment, and evidence checks.

The City of Vancouver CSV is much cleaner than the UBC inventory, but it has one unmapped
row, a few implausible diameters, and a height field that is not independent of LiDAR.
This module keeps the source values, adds evidence flags, and reports the comparison.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from fresh_urban_forest.inventory import enrich_trees, load_vancouver_trees
from fresh_urban_forest.models import TreeRecord
from fresh_urban_forest.terrain import read_raster

DBH_OUTLIER_CM = 300.0
HEIGHT_OUTLIER_M = 80.0


@dataclass(frozen=True, slots=True)
class CityInventory:
    """A normalised City of Vancouver inventory with evidence flags.

    Attributes
    ----------
    trees : tuple of TreeRecord
        Mapped and enriched trees.
    source_rows : int
        Rows in the source CSV.
    unmapped_rows : int
        Rows without usable coordinates.
    dbh_outliers : int
        Rows with DBH above :data:`DBH_OUTLIER_CM`.
    height_outliers : int
        Rows with height above :data:`HEIGHT_OUTLIER_M`.
    """

    trees: tuple[TreeRecord, ...]
    source_rows: int
    unmapped_rows: int
    dbh_outliers: int
    height_outliers: int


def load_city_inventory(path: Path) -> CityInventory:
    """Load the full Vancouver public-tree CSV and flag outliers.

    Parameters
    ----------
    path : Path
        Public-tree CSV export.

    Returns
    -------
    CityInventory
        Normalised inventory.
    """
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        source_rows = sum(1 for _ in csv.DictReader(handle))
    trees = load_vancouver_trees(path)
    flagged: list[TreeRecord] = []
    dbh_outliers = 0
    height_outliers = 0
    for tree in trees:
        attributes = dict(tree.attributes)
        dbh_outlier = tree.dbh_cm is not None and tree.dbh_cm > DBH_OUTLIER_CM
        height_outlier = tree.height_m is not None and tree.height_m > HEIGHT_OUTLIER_M
        if dbh_outlier:
            dbh_outliers += 1
            attributes["dbh_outlier"] = "true"
        if height_outlier:
            height_outliers += 1
            attributes["height_outlier"] = "true"
        attributes.setdefault("city", "Vancouver")
        flagged.append(replace(tree, attributes=attributes))
    return CityInventory(
        trees=tuple(flagged),
        source_rows=source_rows,
        unmapped_rows=max(0, source_rows - len(flagged)),
        dbh_outliers=dbh_outliers,
        height_outliers=height_outliers,
    )


def enrich_city_inventory(
    inventory: CityInventory,
    *,
    dem_path: Path,
    chm_path: Path,
) -> CityInventory:
    """Attach projected coordinates, ground elevation, and LiDAR height.

    Parameters
    ----------
    inventory : CityInventory
        Source inventory.
    dem_path : Path
        City 1 m DEM.
    chm_path : Path
        City 1 m CHM.

    Returns
    -------
    CityInventory
        Enriched inventory.
    """
    dem = read_raster(dem_path)
    chm = read_raster(chm_path)
    enriched = enrich_trees(inventory.trees, dem, chm)
    return replace(inventory, trees=enriched)


def inventory_summary(inventory: CityInventory) -> dict[str, object]:
    """Summarise completeness, species, and the inventory-to-LiDAR height comparison.

    Parameters
    ----------
    inventory : CityInventory
        Inventory, optionally enriched.

    Returns
    -------
    dict
        JSON-safe summary.
    """
    trees = inventory.trees
    heights = [
        float(tree.height_m) for tree in trees if tree.height_m is not None and tree.height_m > 0.5
    ]
    dbhs = [
        float(tree.dbh_cm)
        for tree in trees
        if tree.dbh_cm is not None and tree.dbh_cm > 0.5 and not _is_outlier(tree, "dbh")
    ]
    species = [tree.species or tree.common_name or "Unknown" for tree in trees]
    local_areas = [tree.attributes.get("local_area", "") for tree in trees]
    return {
        "source_rows": inventory.source_rows,
        "mapped_rows": len(trees),
        "unmapped_rows": inventory.unmapped_rows,
        "dbh_outliers": inventory.dbh_outliers,
        "height_outliers": inventory.height_outliers,
        "height_non_null": len(heights),
        "height_median_m": round(float(np.median(heights)), 3) if heights else 0.0,
        "height_p95_m": round(float(np.percentile(heights, 95)), 3) if heights else 0.0,
        "dbh_non_null": len(dbhs),
        "dbh_median_cm": round(float(np.median(dbhs)), 3) if dbhs else 0.0,
        "species_count": len({value for value in species if value != "Unknown"}),
        "native_fraction": round(
            sum(1 for tree in trees if tree.native) / max(1, len(trees)),
            4,
        ),
        "local_area_count": len({value for value in local_areas if value}),
        "measured_species": _measured_count(trees, "species"),
        "measured_dbh": _measured_count(trees, "dbh"),
        "measured_height": _measured_count(trees, "height"),
        "measured_crown_width": _measured_count(trees, "crown_width"),
        "height_comparison": height_comparison(trees),
    }


def height_comparison(trees: tuple[TreeRecord, ...]) -> dict[str, object]:
    """Compare inventory height with sampled LiDAR canopy height.

    Parameters
    ----------
    trees : tuple of TreeRecord
        Enriched trees.

    Returns
    -------
    dict
        Overall and per-local-area bias, RMSE, MAE, and sample count.
    """
    overall = _height_stats(trees)
    by_area: dict[str, dict[str, float | int]] = {}
    groups: dict[str, list[TreeRecord]] = {}
    for tree in trees:
        area = tree.attributes.get("local_area", "")
        if area:
            groups.setdefault(area, []).append(tree)
    for area, group in sorted(groups.items()):
        by_area[area] = _height_stats(tuple(group))
    return {"overall": overall, "by_local_area": by_area}


def _height_stats(trees: tuple[TreeRecord, ...]) -> dict[str, float | int]:
    """Calculate height error statistics for a tree group."""
    pairs = [
        (tree.height_m, tree.lidar_height_m)
        for tree in trees
        if tree.height_m is not None
        and tree.lidar_height_m is not None
        and tree.height_m > 0.5
        and tree.lidar_height_m > 0.5
    ]
    if not pairs:
        return {"n": 0, "bias_m": 0.0, "rmse_m": 0.0, "mae_m": 0.0, "p95_abs_m": 0.0}
    inventory = np.asarray([pair[0] for pair in pairs], dtype=np.float64)
    lidar = np.asarray([pair[1] for pair in pairs], dtype=np.float64)
    error = inventory - lidar
    return {
        "n": len(pairs),
        "bias_m": round(float(np.mean(error)), 3),
        "rmse_m": round(float(np.sqrt(np.mean(error * error))), 3),
        "mae_m": round(float(np.mean(np.abs(error))), 3),
        "p95_abs_m": round(float(np.percentile(np.abs(error), 95)), 3),
    }


def _measured_count(trees: tuple[TreeRecord, ...], field: str) -> int:
    """Count trees with a measured flag for a field."""
    return sum(
        1
        for tree in trees
        if str(tree.attributes.get(f"{field}_measured", "")).strip().lower() in {"true", "1"}
    )


def _is_outlier(tree: TreeRecord, field: str) -> bool:
    """Return whether a tree is flagged as an outlier for a field."""
    return str(tree.attributes.get(f"{field}_outlier", "")).strip().lower() == "true"
