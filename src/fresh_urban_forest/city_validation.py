"""Held-out validation and orthophoto audit sampling for city candidates.

The validation design is fixed in ``notes/p32-validation-protocol.md``. This module
implements the deterministic pieces: spatial block selection, equal-area public-tree
sampling, nearest-crown recall, Wilson intervals, and a stratified candidate audit sample.
It does not inspect imagery or make a precision claim.
"""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import geopandas as gpd
import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import Point

from fresh_urban_forest.itd import DetectedTree
from fresh_urban_forest.models import TreeRecord
from fresh_urban_forest.terrain import project_lonlat

VALIDATION_SEED = "p32-2026-11-05"
BLOCK_M = 500.0
BLOCK_BUFFER_M = 100.0
PUBLIC_SAMPLE_SIZE = 1_000
AUDIT_SAMPLE_SIZE = 300


@dataclass(frozen=True, slots=True)
class HeldOutTree:
    """One public tree in the fixed held-out sample.

    Attributes
    ----------
    tree : TreeRecord
        Public tree record.
    local_area : str
        Local-area name used as the sampling stratum.
    """

    tree: TreeRecord
    local_area: str


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Return a Wilson score interval for a binomial proportion.

    Parameters
    ----------
    successes : int
        Number of successes.
    total : int
        Number of trials.
    z : float, optional
        Normal quantile; 1.96 gives a 95% interval.

    Returns
    -------
    tuple of float
        Lower and upper bounds, or ``(0.0, 0.0)`` when ``total`` is zero.
    """
    if total <= 0:
        return (0.0, 0.0)
    proportion = successes / total
    denominator = 1.0 + z * z / total
    centre = (proportion + z * z / (2.0 * total)) / denominator
    half = (
        z
        * math.sqrt(proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total))
        / denominator
    )
    return (max(0.0, centre - half), min(1.0, centre + half))


def block_key(
    x: float,
    y: float,
    bounds: tuple[float, float, float, float],
    *,
    cell_m: float = BLOCK_M,
) -> tuple[int, int]:
    """Return the deterministic block column and row for a projected point.

    Parameters
    ----------
    x : float
        Easting.
    y : float
        Northing.
    bounds : tuple of float
        ``(left, bottom, right, top)``.
    cell_m : float, optional
        Block side in metres.

    Returns
    -------
    tuple of int
        Block column and row.
    """
    left, bottom, _, _ = bounds
    return (math.floor((x - left) / cell_m), math.floor((y - bottom) / cell_m))


def is_held_out_block(
    block: tuple[int, int],
    *,
    seed: str = VALIDATION_SEED,
    modulus: int = 4,
) -> bool:
    """Return whether a block is in the fixed held-out quarter.

    Parameters
    ----------
    block : tuple of int
        Block column and row.
    seed : str, optional
        Fixed hash seed.
    modulus : int, optional
        One block in ``modulus`` is held out.

    Returns
    -------
    bool
        True when the block is held out.
    """
    column, row = block
    digest = hashlib.sha256(f"{seed}:{column}_{row}".encode()).hexdigest()
    return int(digest[:8], 16) % modulus == 0


def is_held_out_point(
    x: float,
    y: float,
    bounds: tuple[float, float, float, float],
    *,
    cell_m: float = BLOCK_M,
    buffer_m: float = BLOCK_BUFFER_M,
    seed: str = VALIDATION_SEED,
) -> bool:
    """Return whether a point is in a held-out block and away from its edge.

    Parameters
    ----------
    x : float
        Easting.
    y : float
        Northing.
    bounds : tuple of float
        ``(left, bottom, right, top)``.
    cell_m : float, optional
        Block side in metres.
    buffer_m : float, optional
        Minimum distance to a block edge.
    seed : str, optional
        Fixed hash seed.

    Returns
    -------
    bool
        True when the point belongs to the fixed validation sample frame.
    """
    column, row = block_key(x, y, bounds, cell_m=cell_m)
    if not is_held_out_block((column, row), seed=seed):
        return False
    left, bottom, _, _ = bounds
    block_left = left + column * cell_m
    block_bottom = bottom + row * cell_m
    return (
        min(
            x - block_left,
            block_left + cell_m - x,
            y - block_bottom,
            block_bottom + cell_m - y,
        )
        >= buffer_m
    )


def _stable_rank(identifier: str, seed: str) -> str:
    return hashlib.sha256(f"{seed}:{identifier}".encode()).hexdigest()


def _as_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _local_area_lookup(
    x_coords: Sequence[float],
    y_coords: Sequence[float],
    local_areas: gpd.GeoDataFrame,
) -> list[str | None]:
    if not len(x_coords):
        return []
    points = gpd.GeoDataFrame(
        {"index": list(range(len(x_coords)))},
        geometry=[Point(x, y) for x, y in zip(x_coords, y_coords, strict=True)],
        crs=local_areas.crs,
    )
    joined = gpd.sjoin(points, local_areas[["name", "geometry"]], how="left", predicate="within")
    result: list[str | None] = [None] * len(x_coords)
    for index, name in zip(joined.index, joined["name"], strict=True):
        if result[int(index)] is None and isinstance(name, str):
            result[int(index)] = name
    return result


def sample_public_trees(
    trees: Sequence[TreeRecord],
    local_areas: gpd.GeoDataFrame,
    bounds: tuple[float, float, float, float],
    *,
    sample_size: int = PUBLIC_SAMPLE_SIZE,
    seed: str = VALIDATION_SEED,
) -> tuple[HeldOutTree, ...]:
    """Sample live public trees from held-out blocks, stratified by local area.

    Parameters
    ----------
    trees : sequence of TreeRecord
        Public inventory.
    local_areas : geopandas.GeoDataFrame
        Local-area polygons with a ``name`` column, in the tree CRS.
    bounds : tuple of float
        City bounds in metres.
    sample_size : int, optional
        Target sample size.
    seed : str, optional
        Fixed sampling seed.

    Returns
    -------
    tuple of HeldOutTree
        Deterministic held-out sample.
    """
    candidates: list[TreeRecord] = []
    for tree in trees:
        if tree.status in {"removed", "dead"} or tree.x_m is None or tree.y_m is None:
            continue
        if is_held_out_point(tree.x_m, tree.y_m, bounds, seed=seed):
            candidates.append(tree)
    lookup = _local_area_lookup(
        [tree.x_m if tree.x_m is not None else 0.0 for tree in candidates],
        [tree.y_m if tree.y_m is not None else 0.0 for tree in candidates],
        local_areas,
    )
    by_area: dict[str, list[TreeRecord]] = defaultdict(list)
    for tree, area in zip(candidates, lookup, strict=True):
        if isinstance(area, str):
            by_area[area].append(tree)
    if not by_area:
        return ()
    area_names = sorted(by_area)
    base = sample_size // len(area_names)
    remainder = sample_size % len(area_names)
    chosen: list[HeldOutTree] = []
    chosen_ids: set[str] = set()
    leftovers: list[tuple[str, TreeRecord]] = []
    for index, area in enumerate(area_names):
        target = base + (1 if index < remainder else 0)
        pool = sorted(by_area[area], key=lambda tree: _stable_rank(tree.tree_id, seed))
        for tree in pool[:target]:
            chosen.append(HeldOutTree(tree, area))
            chosen_ids.add(tree.tree_id)
        leftovers.extend((area, tree) for tree in pool[target:])
    if len(chosen) < sample_size and leftovers:
        for area, tree in sorted(leftovers, key=lambda item: _stable_rank(item[1].tree_id, seed)):
            if tree.tree_id in chosen_ids:
                continue
            chosen.append(HeldOutTree(tree, area))
            chosen_ids.add(tree.tree_id)
            if len(chosen) >= sample_size:
                break
    return tuple(chosen)


def evaluate_public_recall(
    sample: Sequence[HeldOutTree],
    detected: Sequence[DetectedTree],
    *,
    max_distance_m: float = 5.0,
) -> dict[str, object]:
    """Evaluate nearest-crown recall on the held-out public sample.

    Parameters
    ----------
    sample : sequence of HeldOutTree
        Fixed held-out public sample.
    detected : sequence of DetectedTree
        Full-city detected crowns.
    max_distance_m : float, optional
        Recall distance threshold.

    Returns
    -------
    dict
        Recall, Wilson interval, nearest-distance summaries, and by-area counts.
    """
    if not sample or not detected:
        return {
            "sample_size": len(sample),
            "hit_count": 0,
            "recall": 0.0,
            "wilson_low": 0.0,
            "wilson_high": 0.0,
            "max_distance_m": max_distance_m,
            "by_area": {},
            "nearest_distance_p50_m": None,
            "nearest_distance_p95_m": None,
        }
    detected_xy = np.asarray([[tree.x, tree.y] for tree in detected], dtype=np.float64)
    sampled_xy = np.asarray([[item.tree.x_m, item.tree.y_m] for item in sample], dtype=np.float64)
    distances, _ = cKDTree(detected_xy).query(sampled_xy, k=1)
    hits = distances <= max_distance_m
    by_area: dict[str, dict[str, int]] = {}
    for item, hit in zip(sample, hits, strict=True):
        bucket = by_area.setdefault(item.local_area, {"sample": 0, "hits": 0})
        bucket["sample"] += 1
        bucket["hits"] += int(hit)
    low, high = wilson_interval(int(hits.sum()), len(sample))
    matched_distances = distances[hits]
    return {
        "sample_size": len(sample),
        "hit_count": int(hits.sum()),
        "recall": round(float(hits.mean()), 4),
        "wilson_low": round(low, 4),
        "wilson_high": round(high, 4),
        "max_distance_m": max_distance_m,
        "nearest_distance_p50_m": round(float(np.percentile(matched_distances, 50)), 2)
        if len(matched_distances)
        else None,
        "nearest_distance_p95_m": round(float(np.percentile(matched_distances, 95)), 2)
        if len(matched_distances)
        else None,
        "by_area": {
            area: {
                "sample": bucket["sample"],
                "hits": bucket["hits"],
                "recall": round(bucket["hits"] / bucket["sample"], 4),
            }
            for area, bucket in sorted(by_area.items())
        },
    }


def sample_candidate_audit(
    features: Sequence[Mapping[str, object]],
    local_areas: gpd.GeoDataFrame,
    bounds: tuple[float, float, float, float],
    *,
    sample_size: int = AUDIT_SAMPLE_SIZE,
    seed: str = VALIDATION_SEED,
) -> tuple[dict[str, object], ...]:
    """Draw a fixed candidate sample stratified by confidence and land proxy.

    Parameters
    ----------
    features : sequence of mapping
        Candidate GeoJSON features.
    local_areas : geopandas.GeoDataFrame
        Local-area polygons with a ``name`` column, in the tree CRS.
    bounds : tuple of float
        City bounds in metres.
    sample_size : int, optional
        Target audit sample size.
    seed : str, optional
        Fixed sampling seed.

    Returns
    -------
    tuple of dict
        Audit sample with geometry, attributes, and a local-area label.
    """
    rows: list[dict[str, object]] = []
    for feature in features:
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(properties, Mapping) or not isinstance(geometry, Mapping):
            continue
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, Sequence) or len(coordinates) < 2:
            continue
        lon = float(str(coordinates[0]))
        lat = float(str(coordinates[1]))
        x, y = project_lonlat(lon, lat, "EPSG:3157")
        if not is_held_out_point(x, y, bounds, seed=seed):
            continue
        confidence = _as_float(properties.get("confidence", 0.0))
        band = "low" if confidence < 0.5 else "medium" if confidence < 0.7 else "high"
        rows.append(
            {
                "candidate_id": str(properties.get("candidate_id", "")),
                "lon": lon,
                "lat": lat,
                "x_m": x,
                "y_m": y,
                "height_m": _as_float(properties.get("height_m", 0.0)),
                "crown_radius_m": _as_float(properties.get("crown_radius_m", 0.0)),
                "confidence": confidence,
                "confidence_band": band,
                "land_class": str(properties.get("land_class", "unknown")),
            }
        )
    if not rows:
        return ()
    lookup = _local_area_lookup(
        [_as_float(row["x_m"]) for row in rows],
        [_as_float(row["y_m"]) for row in rows],
        local_areas,
    )
    for row, area in zip(rows, lookup, strict=True):
        row["local_area"] = area or "Unknown"
    bands = ("low", "medium", "high")
    land_classes = (
        "likely private parcel",
        "street/lane",
        "public park",
        "other parcel",
        "unknown",
    )
    per_cell = sample_size // (len(bands) * len(land_classes))
    chosen: list[dict[str, object]] = []
    chosen_ids: set[str] = set()
    leftovers: list[dict[str, object]] = []
    for band in bands:
        for land_class in land_classes:
            pool = [
                row
                for row in rows
                if row["confidence_band"] == band and row["land_class"] == land_class
            ]
            pool.sort(key=lambda row: _stable_rank(str(row["candidate_id"]), seed))
            chosen.extend(pool[:per_cell])
            chosen_ids.update(str(row["candidate_id"]) for row in pool[:per_cell])
            leftovers.extend(pool[per_cell:])
    if len(chosen) < sample_size:
        leftovers.sort(key=lambda row: _stable_rank(str(row["candidate_id"]), seed))
        for row in leftovers:
            if str(row["candidate_id"]) in chosen_ids:
                continue
            chosen.append(row)
            chosen_ids.add(str(row["candidate_id"]))
            if len(chosen) >= sample_size:
                break
    return tuple(chosen)


def audit_sample_json(sample: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Build a JSON-safe audit packet summary.

    Parameters
    ----------
    sample : sequence of mapping
        Candidate audit rows.

    Returns
    -------
    dict
        Summary and rows.
    """
    from collections import Counter

    band_counts = Counter(str(row.get("confidence_band")) for row in sample)
    land_counts = Counter(str(row.get("land_class")) for row in sample)
    return {
        "schema_version": "fresh-urban-forest.off-inventory.audit.v1",
        "sample_size": len(sample),
        "confidence_bands": dict(sorted(band_counts.items())),
        "land_classes": dict(sorted(land_counts.items())),
        "status": "packet prepared; imagery inspection pending",
        "rows": list(sample),
    }
