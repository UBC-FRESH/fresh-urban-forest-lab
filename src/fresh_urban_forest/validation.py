"""Validate CHM tree detection against an inventory.

The matching rule is deliberately simple and stated in the output: each detected crown is
matched to the nearest unmatched live inventory tree within a distance tolerance, highest
crown first. This is a screening assessment, not an optimal assignment.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from fresh_urban_forest.itd import DetectedTree
from fresh_urban_forest.models import TreeRecord

VALIDATION_SCHEMA_VERSION = "fresh-urban-forest.validation.v1"


@dataclass(frozen=True, slots=True)
class DetectionMatch:
    """One detected-crown to inventory-tree match.

    Attributes
    ----------
    detected_id : str
        Detected tree identifier.
    tree_id : str
        Inventory tree identifier.
    lon : float
        Detected longitude.
    lat : float
        Detected latitude.
    distance_m : float
        Planar distance between the detected and inventory positions.
    detected_height_m : float
        Detected canopy height.
    inventory_height_m : float
        Inventory height, or zero when missing.
    height_delta_m : float
        Detected minus inventory height.
    detected_crown_radius_m : float
        Detected equivalent crown radius.
    inventory_crown_radius_m : float
        Inventory crown width divided by two, or zero when missing.
    crown_radius_delta_m : float
        Detected minus inventory crown radius.
    """

    detected_id: str
    tree_id: str
    lon: float
    lat: float
    distance_m: float
    detected_height_m: float
    inventory_height_m: float
    height_delta_m: float
    detected_crown_radius_m: float
    inventory_crown_radius_m: float
    crown_radius_delta_m: float


@dataclass(frozen=True, slots=True)
class DetectionValidation:
    """Summary of a detection-versus-inventory assessment.

    Attributes
    ----------
    schema_version : str
        Result schema.
    max_distance_m : float
        Matching tolerance.
    detected_count : int
        Number of detected crowns in the assessment area.
    inventory_count : int
        Number of live inventory trees in the assessment area.
    matched_count : int
        Number of one-to-one matches.
    precision : float
        Matched divided by detected.
    recall : float
        Matched divided by inventory.
    f1 : float
        Harmonic mean of precision and recall.
    mean_distance_m : float
        Mean match distance.
    mean_height_delta_m : float
        Mean detected-minus-inventory height on matched trees.
    height_rmse_m : float
        Root-mean-square height difference on matched trees.
    mean_crown_radius_delta_m : float
        Mean detected-minus-inventory crown-radius difference.
    matches : tuple of DetectionMatch
        The matched pairs.
    unmatched_detected : tuple of str
        Detected identifiers without an inventory match.
    unmatched_inventory : tuple of str
        Inventory identifiers without a detected match.
    method : str
        The matching rule, stated explicitly.
    """

    schema_version: str
    max_distance_m: float
    detected_count: int
    inventory_count: int
    matched_count: int
    precision: float
    recall: float
    f1: float
    mean_distance_m: float
    mean_height_delta_m: float
    height_rmse_m: float
    mean_crown_radius_delta_m: float
    matches: tuple[DetectionMatch, ...]
    unmatched_detected: tuple[str, ...]
    unmatched_inventory: tuple[str, ...]
    method: str


def validate_detection(
    detected: Sequence[DetectedTree],
    trees: Sequence[TreeRecord],
    *,
    max_distance_m: float = 5.0,
    bbox_wgs84: tuple[float, float, float, float] | None = None,
) -> DetectionValidation:
    """Match detected crowns to live inventory trees.

    Parameters
    ----------
    detected : sequence of DetectedTree
        Detected crowns.
    trees : sequence of TreeRecord
        Inventory trees.
    max_distance_m : float
        Maximum planar match distance in metres.
    bbox_wgs84 : tuple of float or None
        Optional inventory filter.

    Returns
    -------
    DetectionValidation
        Matching summary and pairs.
    """
    inventory = [
        tree
        for tree in trees
        if tree.status not in {"removed", "dead"}
        and tree.x_m is not None
        and tree.y_m is not None
        and (
            bbox_wgs84 is None
            or (
                bbox_wgs84[0] <= tree.lon <= bbox_wgs84[2]
                and bbox_wgs84[1] <= tree.lat <= bbox_wgs84[3]
            )
        )
    ]
    available = {tree.tree_id: tree for tree in inventory}
    matches: list[DetectionMatch] = []
    unmatched_detected: list[str] = []
    for crown in sorted(detected, key=lambda item: -item.height_m):
        if not available:
            unmatched_detected.append(crown.tree_id)
            continue
        best_id, best_distance = _nearest(crown, available)
        if best_id is None or best_distance > max_distance_m:
            unmatched_detected.append(crown.tree_id)
            continue
        tree = available.pop(best_id)
        inventory_height = float(tree.height_m or 0.0)
        inventory_radius = float(tree.crown_width_m or 0.0) / 2.0
        matches.append(
            DetectionMatch(
                detected_id=crown.tree_id,
                tree_id=tree.tree_id,
                lon=crown.lon,
                lat=crown.lat,
                distance_m=round(best_distance, 3),
                detected_height_m=round(crown.height_m, 3),
                inventory_height_m=round(inventory_height, 3),
                height_delta_m=round(crown.height_m - inventory_height, 3),
                detected_crown_radius_m=round(crown.crown_radius_m, 3),
                inventory_crown_radius_m=round(inventory_radius, 3),
                crown_radius_delta_m=round(crown.crown_radius_m - inventory_radius, 3),
            )
        )
    matched = len(matches)
    detected_count = len(detected)
    inventory_count = len(inventory)
    precision = matched / detected_count if detected_count else 0.0
    recall = matched / inventory_count if inventory_count else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    distances = np.asarray([match.distance_m for match in matches], dtype=np.float64)
    height_deltas = np.asarray([match.height_delta_m for match in matches], dtype=np.float64)
    crown_deltas = np.asarray([match.crown_radius_delta_m for match in matches], dtype=np.float64)
    return DetectionValidation(
        schema_version=VALIDATION_SCHEMA_VERSION,
        max_distance_m=max_distance_m,
        detected_count=detected_count,
        inventory_count=inventory_count,
        matched_count=matched,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        mean_distance_m=round(float(np.mean(distances)), 3) if matched else 0.0,
        mean_height_delta_m=round(float(np.mean(height_deltas)), 3) if matched else 0.0,
        height_rmse_m=round(float(np.sqrt(np.mean(height_deltas**2))), 3) if matched else 0.0,
        mean_crown_radius_delta_m=(round(float(np.mean(crown_deltas)), 3) if matched else 0.0),
        matches=tuple(matches),
        unmatched_detected=tuple(unmatched_detected),
        unmatched_inventory=tuple(sorted(available)),
        method=(
            "Greedy nearest match, highest detected crown first, one inventory tree per "
            "detected crown; allowed distance is the stated tolerance."
        ),
    )


def write_validation(result: DetectionValidation, out_dir: Path) -> Path:
    """Write a validation JSON and a match/unmatch GeoJSON.

    Parameters
    ----------
    result : DetectionValidation
        Validation result.
    out_dir : Path
        Destination directory.

    Returns
    -------
    Path
        The written JSON path.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = asdict(result)
    path = out_dir / "detection_validation.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (out_dir / "detection_validation.geojson").write_text(
        json.dumps(_validation_geojson(result), indent=1) + "\n", encoding="utf-8"
    )
    return path


def _nearest(
    crown: DetectedTree,
    trees: dict[str, TreeRecord],
) -> tuple[str | None, float]:
    """Find the nearest inventory tree to a detected crown.

    Parameters
    ----------
    crown : DetectedTree
        Detected crown.
    trees : dict of str to TreeRecord
        Available inventory trees.

    Returns
    -------
    tuple of str or None and float
        Nearest tree id and distance, or ``None`` and infinity when the dict is empty.
    """
    best_id: str | None = None
    best_distance = float("inf")
    for tree_id, tree in trees.items():
        if tree.x_m is None or tree.y_m is None:
            continue
        distance = float(np.hypot(tree.x_m - crown.x, tree.y_m - crown.y))
        if distance < best_distance:
            best_id = tree_id
            best_distance = distance
    return (best_id, best_distance)


def _validation_geojson(result: DetectionValidation) -> dict[str, object]:
    """Build a GeoJSON collection of matches and unmatched crowns.

    Parameters
    ----------
    result : DetectionValidation
        Validation result.

    Returns
    -------
    dict
        GeoJSON FeatureCollection.
    """
    features = []
    for match in result.matches:
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [match.lon, match.lat]},
                "properties": {
                    "status": "matched",
                    "detected_id": match.detected_id,
                    "tree_id": match.tree_id,
                    "distance_m": match.distance_m,
                    "height_delta_m": match.height_delta_m,
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}
