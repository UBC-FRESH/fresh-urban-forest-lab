"""City-scale ALS off-inventory candidate detection and land-context labelling.

This module extends the P9 pilot from a small Main Mall patch to the full city. It uses the
P30 1 m CHM (downsampled for detection) and the City parcel, parks, and zoning layers. The
result is a candidate inventory, not a census and not an ownership layer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from numpy.typing import NDArray
from scipy.spatial import cKDTree
from shapely.geometry import Point

from fresh_urban_forest.itd import DetectedTree, detect_trees
from fresh_urban_forest.models import TerrainGrid, TreeRecord
from fresh_urban_forest.off_inventory import OffInventoryCandidate
from fresh_urban_forest.terrain import read_raster

CITY_DETECTION_RESOLUTION_M = 2.0
CITY_DETECTION_TILE_M = 1000.0
CITY_DETECTION_BUFFER_M = 40.0


@dataclass(frozen=True, slots=True)
class CityMatch:
    """One-to-one public-tree match result.

    Attributes
    ----------
    matched: int
        Number of detected crowns matched to a public tree.
    unmatched_detected: tuple of str
        Detected IDs without a public-tree match.
    unmatched_inventory: tuple of str
        Public-tree IDs without a detected match.
    """

    matched: int
    unmatched_detected: tuple[str, ...]
    unmatched_inventory: tuple[str, ...]


def detect_city_trees(
    chm_path: Path,
    *,
    resolution_m: float = CITY_DETECTION_RESOLUTION_M,
    tile_m: float = CITY_DETECTION_TILE_M,
    buffer_m: float = CITY_DETECTION_BUFFER_M,
    window_m: float = 5.0,
    min_height_m: float = 3.0,
) -> tuple[DetectedTree, ...]:
    """Detect crowns on the full city CHM with overlapping tiles.

    Parameters
    ----------
    chm_path : Path
        City 1 m CHM.
    resolution_m : float
        Detection cell size. The 1 m CHM is block-max downsampled to this size.
    tile_m : float
        Core tile side in metres.
    buffer_m : float
        Overlap buffer around each core tile.
    window_m : float
        Local-maxima window in metres.
    min_height_m : float
        Minimum canopy height.

    Returns
    -------
    tuple of DetectedTree
        City crowns with unique ``city-N`` IDs.
    """
    chm = read_raster(chm_path)
    factor = max(1, round(resolution_m))
    full = np.asarray(chm.array, dtype=np.float32)
    height = full.shape[0] // factor
    width = full.shape[1] // factor
    if factor > 1:
        can = np.nanmax(
            full[: height * factor, : width * factor].reshape(height, factor, width, factor),
            axis=(1, 3),
        )
    else:
        can = full
    left, top = chm.bounds[0], chm.bounds[3]
    right, bottom = left + width * factor, top - height * factor
    cols = math.ceil((right - left) / tile_m)
    rows = math.ceil((top - bottom) / tile_m)
    collected: list[DetectedTree] = []
    for row in range(rows):
        for col in range(cols):
            core_left = left + col * tile_m
            core_right = min(right, core_left + tile_m)
            core_top = top - row * tile_m
            core_bottom = max(bottom, core_top - tile_m)
            if core_right <= core_left or core_bottom >= core_top:
                continue
            grid_left = core_left - buffer_m
            grid_right = core_right + buffer_m
            grid_top = core_top + buffer_m
            grid_bottom = core_bottom - buffer_m
            c0 = max(0, int((grid_left - left) / factor))
            c1 = min(width, int((grid_right - left) / factor))
            r0 = max(0, int((top - grid_top) / factor))
            r1 = min(height, int((top - grid_bottom) / factor))
            if c1 <= c0 or r1 <= r0:
                continue
            array = np.asarray(can[r0:r1, c0:c1], dtype=np.float32)
            grid = TerrainGrid(
                crs=chm.crs,
                bounds=(
                    left + c0 * factor,
                    top - r1 * factor,
                    left + c1 * factor,
                    top - r0 * factor,
                ),
                width=array.shape[1],
                height=array.shape[0],
                elevation=np.zeros_like(array),
                canopy_height=array,
            )
            for tree in detect_trees(grid, min_height_m=min_height_m, window_m=window_m):
                if core_left <= tree.x < core_right and core_bottom <= tree.y < core_top:
                    collected.append(tree)
    return tuple(
        replace(tree, tree_id=f"city-{index + 1:07d}") for index, tree in enumerate(collected)
    )


def match_inventory(
    detected: tuple[DetectedTree, ...],
    trees: tuple[TreeRecord, ...],
    *,
    max_distance_m: float = 5.0,
) -> CityMatch:
    """Match detected crowns to public trees with a spatial KD-tree.

    Parameters
    ----------
    detected : tuple of DetectedTree
        Detected crowns.
    trees : tuple of TreeRecord
        Public tree inventory.
    max_distance_m : float
        Maximum match distance.

    Returns
    -------
    CityMatch
        One-to-one match summary.
    """
    inventory = [
        tree
        for tree in trees
        if tree.status not in {"removed", "dead"} and tree.x_m is not None and tree.y_m is not None
    ]
    if not detected or not inventory:
        return CityMatch(
            matched=0,
            unmatched_detected=tuple(tree.tree_id for tree in detected),
            unmatched_inventory=tuple(tree.tree_id for tree in inventory),
        )
    tree_xy = np.asarray([[tree.x_m, tree.y_m] for tree in inventory], dtype=np.float64)
    det_xy = np.asarray([[tree.x, tree.y] for tree in detected], dtype=np.float64)
    tree_index = cKDTree(tree_xy)
    distances, indices = tree_index.query(det_xy, k=1, distance_upper_bound=max_distance_m)
    pairs = [
        (float(distance), detected_index, int(index))
        for detected_index, (distance, index) in enumerate(zip(distances, indices, strict=True))
        if math.isfinite(distance) and index < len(inventory)
    ]
    pairs.sort()
    used_trees: set[int] = set()
    used_detected: set[int] = set()
    for _, detected_index, inventory_index in pairs:
        if detected_index in used_detected or inventory_index in used_trees:
            continue
        used_detected.add(detected_index)
        used_trees.add(inventory_index)
    return CityMatch(
        matched=len(used_detected),
        unmatched_detected=tuple(
            tree.tree_id for index, tree in enumerate(detected) if index not in used_detected
        ),
        unmatched_inventory=tuple(
            tree.tree_id for index, tree in enumerate(inventory) if index not in used_trees
        ),
    )


def classify_land_context(
    xs: NDArray[np.float64],
    ys: NDArray[np.float64],
    *,
    parcels_path: Path,
    parks_path: Path,
    roads_path: Path,
    zoning_path: Path,
    crs: str = "EPSG:3157",
    road_buffer_m: float = 7.5,
) -> list[str]:
    """Label candidate points with a public/private land-context proxy.

    Parameters
    ----------
    xs, ys : numpy.ndarray
        Projected candidate coordinates.
    parcels_path : Path
        Property parcel polygons.
    parks_path : Path
        Park polygons.
    roads_path : Path
        OSM road centreline GeoJSON.
    zoning_path : Path
        Zoning polygons.
    crs : str
        Projected CRS.
    road_buffer_m : float
        Street/lane buffer.

    Returns
    -------
    list of str
        ``public park``, ``street/lane``, ``likely private parcel``,
        ``other parcel``, or ``unknown``.
    """
    points = gpd.GeoDataFrame(geometry=[Point(x, y) for x, y in zip(xs, ys, strict=True)], crs=crs)
    labels = np.full(len(points), "unknown", dtype=object)
    parks = gpd.read_file(parks_path).to_crs(crs)
    roads = gpd.read_file(roads_path).to_crs(crs)
    parcels = gpd.read_file(parcels_path).to_crs(crs)
    zoning = gpd.read_file(zoning_path).to_crs(crs)
    park_hits = gpd.sjoin(points, parks[["geometry"]], how="left", predicate="within")
    park_mask = np.zeros(len(points), dtype=bool)
    park_mask[park_hits.loc[park_hits.index_right.notna()].index.unique()] = True
    labels[park_mask] = "public park"
    road_buffers = roads.geometry.buffer(road_buffer_m)
    road_frame = gpd.GeoDataFrame(geometry=road_buffers, crs=crs)
    road_hits = gpd.sjoin(points, road_frame, how="left", predicate="within")
    road_mask = np.zeros(len(points), dtype=bool)
    road_mask[road_hits.loc[road_hits.index_right.notna()].index.unique()] = True
    labels[road_mask & (labels == "unknown")] = "street/lane"
    parcel_hits = gpd.sjoin(points, parcels[["geometry"]], how="left", predicate="within")
    parcel_mask = np.zeros(len(points), dtype=bool)
    parcel_mask[parcel_hits.loc[parcel_hits.index_right.notna()].index.unique()] = True
    parcel_mask &= labels == "unknown"
    if bool(parcel_mask.any()):
        zone_hits = gpd.sjoin(
            points,
            zoning[["zoning_classification", "zoning_category", "geometry"]],
            how="left",
            predicate="within",
        )
        zone_hits = zone_hits[~zone_hits.index.duplicated(keep="first")]
        classifications = (
            zone_hits["zoning_classification"]
            .fillna("")
            .astype(str)
            .reindex(points.index, fill_value="")
        )
        categories = (
            zone_hits["zoning_category"].fillna("").astype(str).reindex(points.index, fill_value="")
        )
        residential = classifications.str.startswith("Residential") | categories.str.startswith("R")
        residential_values = residential.to_numpy(dtype=bool)
        labels[parcel_mask & residential_values] = "likely private parcel"
        labels[parcel_mask & ~residential_values] = "other parcel"
    return [str(label) for label in labels]


def build_city_candidates(
    detected: tuple[DetectedTree, ...],
    match: CityMatch,
    trees: tuple[TreeRecord, ...],
    land_classes: list[str],
    *,
    building_mask_path: Path | None = None,
    water_mask_path: Path | None = None,
) -> tuple[OffInventoryCandidate, ...]:
    """Build candidate records from unmatched crowns and land-context labels.

    Parameters
    ----------
    detected : tuple of DetectedTree
        City detected crowns.
    match : CityMatch
        Public-inventory match.
    trees : tuple of TreeRecord
        Public trees used for nearest-distance evidence.
    land_classes : list of str
        Land-context label aligned with ``detected``.
    building_mask_path : Path or None
        Optional P30 building mask; crowns whose centre falls on a building are excluded.
    water_mask_path : Path or None
        Optional P30 water mask; crowns whose centre falls on water are excluded.

    Returns
    -------
    tuple of OffInventoryCandidate
        Candidates without an arbitrary cap.
    """
    unmatched = set(match.unmatched_detected)
    inventory_xy = np.asarray(
        [
            [tree.x_m, tree.y_m]
            for tree in trees
            if (
                tree.x_m is not None
                and tree.y_m is not None
                and tree.status not in {"removed", "dead"}
            )
        ],
        dtype=np.float64,
    )
    inventory_tree = cKDTree(inventory_xy) if len(inventory_xy) else None

    def mask_values(path: Path | None) -> NDArray[np.float64] | None:
        if path is None:
            return None
        with rasterio.open(path) as dataset:
            values = [
                float(next(iter(dataset.sample([(crown.x, crown.y)])))[0]) for crown in detected
            ]
        return np.asarray(values, dtype=np.float64)

    building_values = mask_values(building_mask_path)
    water_values = mask_values(water_mask_path)
    candidates: list[OffInventoryCandidate] = []
    for index, crown in enumerate(detected):
        if crown.tree_id not in unmatched:
            continue
        if building_values is not None and building_values[index] > 0:
            continue
        if water_values is not None and water_values[index] > 0:
            continue
        nearest = 1_000.0
        if inventory_tree is not None:
            distance, _ = inventory_tree.query(np.asarray([crown.x, crown.y]), k=1)
            nearest = float(distance)
        height_component = min(crown.height_m / 25.0, 1.0)
        if crown.height_m > 45.0:
            height_component *= 0.35
        if crown.height_m > 60.0:
            height_component = min(height_component, 0.08)
        confidence = round(
            0.4 * height_component
            + 0.3 * min(crown.crown_radius_m / 8.0, 1.0)
            + 0.3 * min(nearest / 20.0, 1.0),
            3,
        )
        land_class = land_classes[index] if index < len(land_classes) else "unknown"
        reasons = [
            f"height {crown.height_m:.1f} m",
            f"crown radius {crown.crown_radius_m:.1f} m",
            f"{nearest:.1f} m from nearest public tree",
            f"{land_class} (land proxy, not ownership)",
        ]
        if crown.height_m > 45.0:
            reasons.append("height outside plausible screening range; review")
        candidates.append(
            OffInventoryCandidate(
                candidate_id=f"off-{len(candidates) + 1:06d}",
                detected_id=crown.tree_id,
                lon=crown.lon,
                lat=crown.lat,
                x_m=crown.x,
                y_m=crown.y,
                height_m=crown.height_m,
                crown_radius_m=crown.crown_radius_m,
                crown_area_m2=crown.crown_area_m2,
                nearest_inventory_m=round(nearest, 2),
                land_class=land_class,
                confidence=confidence,
                reasons=tuple(reasons),
            )
        )
    return tuple(candidates)


def write_city_candidates(
    candidates: tuple[OffInventoryCandidate, ...],
    *,
    dataset_id: str,
    detected_count: int,
    matched_count: int,
    unmatched_inventory_count: int,
    out_dir: Path,
) -> Path:
    """Write a compact city summary and a full compressed candidate GeoJSON.

    Parameters
    ----------
    candidates : tuple of OffInventoryCandidate
        Candidate records.
    dataset_id : str
        Source dataset identifier.
    detected_count : int
        Detected crowns before matching.
    matched_count : int
        Public trees matched one-to-one.
    unmatched_inventory_count : int
        Public trees without a detected match.
    out_dir : Path
        Destination directory.

    Returns
    -------
    Path
        Summary JSON path.
    """
    import gzip
    import json
    from collections import Counter

    from fresh_urban_forest.allometry import (
        carbon_kg,
        crown_volume_m3,
        estimate_dbh_cm,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    class_counts = Counter(candidate.land_class for candidate in candidates)
    confidence = [candidate.confidence for candidate in candidates]
    total_area = sum(candidate.crown_area_m2 for candidate in candidates)
    total_volume = 0.0
    total_carbon = 0.0
    features = []
    for candidate in candidates:
        dbh = estimate_dbh_cm(candidate.height_m, "unknown")
        volume = crown_volume_m3(candidate.height_m, candidate.crown_radius_m * 2.0)
        carbon = carbon_kg(dbh, "unknown")
        total_volume += volume
        total_carbon += carbon
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [candidate.lon, candidate.lat]},
                "properties": {
                    "candidate_id": candidate.candidate_id,
                    "height_m": candidate.height_m,
                    "crown_radius_m": candidate.crown_radius_m,
                    "crown_area_m2": candidate.crown_area_m2,
                    "dbh_cm": round(dbh, 2),
                    "crown_volume_m3": round(volume, 2),
                    "carbon_kg": round(carbon, 2),
                    "confidence": candidate.confidence,
                    "land_class": candidate.land_class,
                    "nearest_inventory_m": candidate.nearest_inventory_m,
                },
            }
        )
    summary = {
        "schema_version": "fresh-urban-forest.off-inventory.city.v1",
        "dataset_id": dataset_id,
        "detected_count": detected_count,
        "matched_count": matched_count,
        "unmatched_inventory_count": unmatched_inventory_count,
        "candidate_count": len(candidates),
        "high_confidence_count": sum(1 for value in confidence if value >= 0.6),
        "candidate_area_m2": round(total_area, 1),
        "candidate_canopy_volume_m3": round(total_volume, 1),
        "candidate_carbon_kg": round(total_carbon, 1),
        "land_classes": dict(sorted(class_counts.items())),
        "confidence_p50": round(float(np.median(confidence)), 3) if confidence else 0.0,
        "confidence_p95": round(float(np.percentile(confidence, 95)), 3) if confidence else 0.0,
        "method": (
            "2 m block-max CHM, tiled local-maxima and watershed, KD-tree public-tree "
            "matching, parcel/parks/zoning/OSM land-context proxy."
        ),
        "evidence": {
            "tier": "screening",
            "caveat": (
                "Candidates include real off-inventory trees, missed public records, and "
                "over-segmentation. They are not a census, not ownership, and not species."
            ),
        },
    }
    summary_path = out_dir / "off_inventory.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with gzip.open(out_dir / "off_inventory.geojson.gz", "wt", encoding="utf-8") as handle:
        json.dump(
            {"type": "FeatureCollection", "features": features},
            handle,
            separators=(",", ":"),
        )
    return summary_path
