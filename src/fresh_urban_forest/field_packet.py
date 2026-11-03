"""Build a field-validation packet for a small reference patch.

The packet is deliberately low-tech: a GeoJSON of inventory trees, a CSV checklist, a
GeoJSON of detected crowns, and a short protocol. A field crew can verify every tree in a
small patch instead of treating the whole inventory as a complete reference.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from pathlib import Path

from fresh_urban_forest.itd import DetectedTree
from fresh_urban_forest.models import TreeRecord
from fresh_urban_forest.validation import DetectionValidation


def build_field_packet(
    trees: Sequence[TreeRecord],
    detected: Sequence[DetectedTree],
    *,
    bbox_wgs84: tuple[float, float, float, float],
    out_dir: Path,
    max_trees: int = 150,
    validation: DetectionValidation | None = None,
) -> Path:
    """Write a field-validation packet for one patch.

    Parameters
    ----------
    trees : sequence of TreeRecord
        Inventory trees.
    detected : sequence of DetectedTree
        Detected crowns.
    bbox_wgs84 : tuple of float
        Patch bounding box.
    out_dir : Path
        Destination directory.
    max_trees : int
        Maximum inventory trees in the checklist.
    validation : DetectionValidation or None
        Optional matching result used to add detected IDs and distances.

    Returns
    -------
    Path
        The written ``README.md`` path.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    selected = sorted(
        [
            tree
            for tree in trees
            if tree.status not in {"removed", "dead"}
            and bbox_wgs84[0] <= tree.lon <= bbox_wgs84[2]
            and bbox_wgs84[1] <= tree.lat <= bbox_wgs84[3]
        ],
        key=lambda tree: tree.tree_id,
    )[:max_trees]
    selected_detected = [
        crown
        for crown in detected
        if bbox_wgs84[0] <= crown.lon <= bbox_wgs84[2]
        and bbox_wgs84[1] <= crown.lat <= bbox_wgs84[3]
    ]
    matches = {match.tree_id: match for match in (validation.matches if validation else ())}
    (out_dir / "field_trees.geojson").write_text(
        json.dumps(_trees_geojson(selected), indent=1) + "\n", encoding="utf-8"
    )
    (out_dir / "detected_crowns.geojson").write_text(
        json.dumps(_crowns_geojson(selected_detected), indent=1) + "\n", encoding="utf-8"
    )
    with (out_dir / "field_checks.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "tree_id",
                "lon",
                "lat",
                "species",
                "dbh_cm",
                "height_m",
                "crown_width_m",
                "dbh_measured",
                "height_measured",
                "crown_width_measured",
                "detected_id",
                "detected_height_m",
                "detected_crown_radius_m",
                "match_distance_m",
                "field_verified",
                "field_notes",
            ]
        )
        for tree in selected:
            match = matches.get(tree.tree_id)
            writer.writerow(
                [
                    tree.tree_id,
                    tree.lon,
                    tree.lat,
                    tree.species,
                    tree.dbh_cm or "",
                    tree.height_m or "",
                    tree.crown_width_m or "",
                    tree.attributes.get("dbh_measured", ""),
                    tree.attributes.get("height_measured", ""),
                    tree.attributes.get("crown_width_measured", ""),
                    match.detected_id if match else "",
                    match.detected_height_m if match else "",
                    match.detected_crown_radius_m if match else "",
                    match.distance_m if match else "",
                    "",
                    "",
                ]
            )
    readme = _readme(
        bbox_wgs84=bbox_wgs84,
        tree_count=len(selected),
        detected_count=len(selected_detected),
        matched_count=len(matches),
    )
    path = out_dir / "README.md"
    path.write_text(readme, encoding="utf-8")
    return path


def _trees_geojson(trees: Sequence[TreeRecord]) -> dict[str, object]:
    """Convert inventory trees to a GeoJSON FeatureCollection.

    Parameters
    ----------
    trees : sequence of TreeRecord
        Trees to convert.

    Returns
    -------
    dict
        GeoJSON FeatureCollection.
    """
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [tree.lon, tree.lat]},
                "properties": {
                    "tree_id": tree.tree_id,
                    "species": tree.species,
                    "common_name": tree.common_name,
                    "dbh_cm": tree.dbh_cm,
                    "height_m": tree.height_m,
                    "crown_width_m": tree.crown_width_m,
                    "dbh_measured": tree.attributes.get("dbh_measured", ""),
                    "height_measured": tree.attributes.get("height_measured", ""),
                    "crown_width_measured": tree.attributes.get("crown_width_measured", ""),
                },
            }
            for tree in trees
        ],
    }


def _crowns_geojson(crowns: Sequence[DetectedTree]) -> dict[str, object]:
    """Convert detected crowns to a GeoJSON FeatureCollection.

    Parameters
    ----------
    crowns : sequence of DetectedTree
        Crowns to convert.

    Returns
    -------
    dict
        GeoJSON FeatureCollection.
    """
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [crown.lon, crown.lat]},
                "properties": {
                    "detected_id": crown.tree_id,
                    "height_m": crown.height_m,
                    "crown_radius_m": crown.crown_radius_m,
                    "crown_area_m2": crown.crown_area_m2,
                },
            }
            for crown in crowns
        ],
    }


def _readme(
    *,
    bbox_wgs84: tuple[float, float, float, float],
    tree_count: int,
    detected_count: int,
    matched_count: int,
) -> str:
    """Build the field protocol text.

    Parameters
    ----------
    bbox_wgs84 : tuple of float
        Patch bounding box.
    tree_count : int
        Inventory trees in the packet.
    detected_count : int
        Detected crowns in the patch.
    matched_count : int
        One-to-one matches.

    Returns
    -------
    str
        Markdown protocol.
    """
    return f"""# Field validation packet

Patch bbox: `{bbox_wgs84[0]}, {bbox_wgs84[1]}, {bbox_wgs84[2]}, {bbox_wgs84[3]}`

- Inventory trees: {tree_count}
- Detected crowns: {detected_count}
- One-to-one matches: {matched_count}

## Purpose

This is a **complete-reference patch** protocol. The goal is to verify every live tree and
every detected crown inside a small area, not to treat the citywide inventory as complete.

## Files

- `field_trees.geojson`: inventory trees in the patch.
- `detected_crowns.geojson`: CHM-detected crowns in the patch.
- `field_checks.csv`: one row per inventory tree with measured flags and match fields.

## Field steps

1. Load both GeoJSON files into QGIS, MapInfo, or a mobile GIS app.
2. Walk the patch and verify every inventory tree. Record `field_verified` as `yes`,
   `no`, or `missing` in the CSV.
3. Add any live tree that is not in the inventory as a new row with a temporary ID.
4. For each detected crown, decide whether it is a real tree, a merged crown, or a
   false positive. Record the decision in `field_notes`.
5. Re-measure DBH, height, and crown width for a subsample, especially trees currently
   flagged as imputed.
6. Return the completed CSV and a photo log.

## Analysis

The completed CSV lets us calculate:

- detection precision against a complete patch;
- detection recall against a complete patch;
- height and crown-width bias;
- inventory omission and commission rates;
- the share of the current canopy estimate that depends on imputed attributes.

Do not pool this patch with the whole-inventory precision numbers. The whole inventory is
not a complete reference.
"""
