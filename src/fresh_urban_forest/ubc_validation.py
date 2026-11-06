"""Independent UBC inventory validation helpers.

This module loads the UBC campus inventory, matches detected crowns one-to-one, and
reports attribute residuals for measured records. It does not tune the City detector.
"""

from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
import numpy as np
from scipy.spatial import cKDTree

from fresh_urban_forest.allometry import estimate_dbh_cm
from fresh_urban_forest.itd import DetectedTree
from fresh_urban_forest.models import TreeRecord
from fresh_urban_forest.terrain import project_lonlat


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


@dataclass(frozen=True, slots=True)
class UbcMatchSummary:
    """One-to-one UBC match result.

    Attributes
    ----------
    eligible : int
        UBC records in the CHM frame.
    matched : int
        Records with a unique detected crown within the distance threshold.
    recall : float
        Matched / eligible.
    missed_nearest_distance_p50_m : float or None
        Median nearest detection distance for missed records.
    missed_nearest_distance_p95_m : float or None
        95th percentile nearest detection distance for missed records.
    """

    eligible: int
    matched: int
    recall: float
    missed_nearest_distance_p50_m: float | None
    missed_nearest_distance_p95_m: float | None


def ubc_tree_records(gdf: gpd.GeoDataFrame) -> tuple[TreeRecord, ...]:
    """Convert the UBC inventory to normalised tree records.

    Parameters
    ----------
    gdf : geopandas.GeoDataFrame
        UBC campus tree inventory in EPSG:4326.

    Returns
    -------
    tuple of TreeRecord
        Live, non-hedge records with projected coordinates.
    """
    frame = gdf[
        (gdf["LIVE_TREE"] != "Dead")
        & (~gdf["TREE_STATUS"].fillna("").str.lower().str.contains("removed|hedge"))
    ]
    trees: list[TreeRecord] = []
    for index, row in frame.iterrows():
        lon = float(row.geometry.x)
        lat = float(row.geometry.y)
        x, y = project_lonlat(lon, lat, "EPSG:3157")
        crown: float | None
        crown_1 = _number(row.get("CROWNWIDTH1"))
        crown_2 = _number(row.get("CROWNWIDTH2"))
        if crown_1 is not None and crown_2 is not None:
            crown = (crown_1 + crown_2) / 2.0
        else:
            crown = crown_1
        trees.append(
            TreeRecord(
                tree_id=str(row.get("TREEID") or index),
                lon=lon,
                lat=lat,
                species=str(row.get("TAXA") or ""),
                common_name=str(row.get("COMMON_NAME") or ""),
                dbh_cm=_number(row.get("DBH")),
                height_m=_number(row.get("THEIGHT")),
                crown_width_m=crown,
                status="alive",
                source="ubc_campus_trees",
                x_m=x,
                y_m=y,
            )
        )
    return tuple(trees)


def one_to_one_matches(
    detected: tuple[DetectedTree, ...],
    trees: tuple[TreeRecord, ...],
    *,
    max_distance_m: float = 5.0,
) -> tuple[dict[int, int], UbcMatchSummary]:
    """Match UBC trees to detected crowns one-to-one.

    Parameters
    ----------
    detected : tuple of DetectedTree
        Detected crowns.
    trees : tuple of TreeRecord
        UBC tree records.
    max_distance_m : float, optional
        Maximum match distance.

    Returns
    -------
    tuple of dict and UbcMatchSummary
        Tree index to detection index mapping, and the recall summary.
    """
    if not detected or not trees:
        return {}, UbcMatchSummary(0, 0, 0.0, None, None)
    detected_xy = np.asarray([[tree.x, tree.y] for tree in detected], dtype=np.float64)
    tree_xy = np.asarray([[tree.x_m or 0.0, tree.y_m or 0.0] for tree in trees], dtype=np.float64)
    tree_index = cKDTree(detected_xy)
    nearest_distances, _ = tree_index.query(tree_xy, k=1)
    distances, indices = tree_index.query(tree_xy, k=1, distance_upper_bound=max_distance_m)
    pairs = sorted(
        (float(distance), index, int(detection_index))
        for index, (distance, detection_index) in enumerate(zip(distances, indices, strict=True))
        if np.isfinite(distance) and detection_index < len(detected)
    )
    used_trees: set[int] = set()
    used_detected: set[int] = set()
    mapping: dict[int, int] = {}
    for _, tree_index, detection_index in pairs:
        if tree_index in used_trees or detection_index in used_detected:
            continue
        used_trees.add(tree_index)
        used_detected.add(detection_index)
        mapping[tree_index] = detection_index
    missed = [index for index in range(len(trees)) if index not in used_trees]
    missed_distances = [float(nearest_distances[index]) for index in missed] if missed else []
    return mapping, UbcMatchSummary(
        eligible=len(trees),
        matched=len(used_trees),
        recall=round(len(used_trees) / len(trees), 4),
        missed_nearest_distance_p50_m=round(float(np.percentile(missed_distances, 50)), 2)
        if missed_distances
        else None,
        missed_nearest_distance_p95_m=round(float(np.percentile(missed_distances, 95)), 2)
        if missed_distances
        else None,
    )


def attribute_errors(
    mapping: dict[int, int],
    detected: tuple[DetectedTree, ...],
    trees: tuple[TreeRecord, ...],
) -> dict[str, object]:
    """Compute matched UBC height, crown, and DBH residuals.

    Parameters
    ----------
    mapping : dict
        Tree index to detection index mapping.
    detected : tuple of DetectedTree
        Detected crowns.
    trees : tuple of TreeRecord
        UBC tree records.

    Returns
    -------
    dict
        Bias, MAE, RMSE, and p5/p95 residuals for each attribute.
    """
    rows: dict[str, list[tuple[float, float]]] = {
        "height_m": [],
        "crown_width_m": [],
        "dbh_cm": [],
    }
    for tree_index, detection_index in mapping.items():
        tree = trees[tree_index]
        crown = detected[detection_index]
        if tree.height_m is not None:
            rows["height_m"].append((crown.height_m, tree.height_m))
        if tree.crown_width_m is not None:
            rows["crown_width_m"].append((crown.crown_radius_m * 2.0, tree.crown_width_m))
        if tree.dbh_cm is not None:
            rows["dbh_cm"].append((estimate_dbh_cm(crown.height_m, "unknown"), tree.dbh_cm))
    result: dict[str, object] = {}
    for key, values in rows.items():
        if not values:
            result[key] = {"n": 0}
            continue
        array = np.asarray(values, dtype=np.float64)
        error = array[:, 0] - array[:, 1]
        result[key] = {
            "n": len(values),
            "bias": round(float(np.mean(error)), 2),
            "mae": round(float(np.mean(np.abs(error))), 2),
            "rmse": round(float(np.sqrt(np.mean(error * error))), 2),
            "p05": round(float(np.percentile(error, 5)), 2),
            "p95": round(float(np.percentile(error, 95)), 2),
        }
    return result
