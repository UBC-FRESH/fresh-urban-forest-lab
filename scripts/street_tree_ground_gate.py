"""Evaluate a level-camera ground-plane sanity gate for street-tree candidates.

The script reconstructs source detections from the cached citywide run, tests depth against
the expected level-ground range at the box bottom, and writes an external sample-only
supported subset. It does not modify the canonical layer.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from dataclasses import replace
from pathlib import Path
from typing import cast

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

from fresh_urban_forest.street_trees import (
    StreetImage,
    ground_plane_range_m,
    ground_plane_ratio,
    is_ground_plane_consistent,
)
from street_tree_pilot import _load_inventory


def _f(value: object) -> float:
    """Convert a JSON scalar to float."""
    return float(cast("str | int | float", value))


def _xy(lon: float, lat: float, origin_lon: float, origin_lat: float) -> tuple[float, float]:
    return (
        (lon - origin_lon) * 111_320.0 * math.cos(math.radians(origin_lat)),
        (lat - origin_lat) * 110_540.0,
    )


def _load_images(cache_path: Path, images_dir: Path) -> dict[str, StreetImage]:
    images = {
        item["image_id"]: StreetImage(**item)
        for item in json.loads(cache_path.read_text(encoding="utf-8"))
    }
    for image_id, image in list(images.items()):
        path = images_dir / f"{image_id}.jpg"
        if not path.is_file():
            continue
        with Image.open(path) as opened:
            images[image_id] = replace(image, width=opened.width, height=opened.height)
    return images


def _source_detection(
    candidate: dict[str, object],
    detections: list[dict[str, object]],
) -> dict[str, object] | None:
    lon, lat = candidate["geometry"]["coordinates"]  # type: ignore[index]
    best: dict[str, object] | None = None
    best_distance = float("inf")
    for detection in detections:
        dx, dy = _xy(
            _f(detection["lon"]),
            _f(detection["lat"]),
            float(lon),
            float(lat),
        )
        distance = math.hypot(dx, dy)
        if distance < best_distance:
            best = detection
            best_distance = distance
    return best


def _candidate_support(
    candidate: dict[str, object],
    by_image: dict[str, list[dict[str, object]]],
    images: dict[str, StreetImage],
    *,
    height_m: float,
    min_ratio: float,
    max_ratio: float,
) -> tuple[int, int, int]:
    properties = candidate["properties"]
    image_ids = properties["image_ids"]  # type: ignore[index]
    lon, lat = candidate["geometry"]["coordinates"]  # type: ignore[index]
    checked = 0
    supported = 0
    above = 0
    for image_id in image_ids:
        image = images.get(str(image_id))
        if image is None:
            continue
        image_detections = by_image.get(str(image_id), [])
        if not image_detections:
            continue
        detection = min(
            image_detections,
            key=lambda item: math.hypot(
                *_xy(
                    _f(item["lon"]),
                    _f(item["lat"]),
                    _f(lon),
                    _f(lat),
                )
            ),
        )
        checked += 1
        y = _f(detection["ymax"])
        expected = ground_plane_range_m(image, y, camera_height_m=height_m)
        if expected is None:
            above += 1
            continue
        if is_ground_plane_consistent(
            image,
            y,
            _f(detection["depth_m"]),
            camera_height_m=height_m,
            min_ratio=min_ratio,
            max_ratio=max_ratio,
        ):
            supported += 1
    return checked, supported, above


def run(args: argparse.Namespace) -> dict[str, object]:
    """Run the ground-plane gate audit.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed audit arguments.

    Returns
    -------
    dict[str, object]
        Audit payload written to disk.
    """
    images = _load_images(args.images_cache, args.images_dir)
    detections = json.loads(args.detections.read_text(encoding="utf-8"))
    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))["features"]
    by_image: dict[str, list[dict[str, object]]] = {}
    for detection in detections:
        by_image.setdefault(str(detection["image_id"]), []).append(detection)
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    audit_by_id: dict[str, dict[str, object]] = {
        str(item["candidate_id"]): item for item in audit["samples"]
    }
    inventory = _load_inventory(args.dataset)
    origin_lon, origin_lat = inventory[0][0], inventory[0][1]
    inventory_points = np.asarray(
        [_xy(lon, lat, origin_lon, origin_lat) for lon, lat, _tree_id in inventory]
    )
    inventory_tree = cKDTree(inventory_points)
    results: dict[str, object] = {}
    for height in args.heights:
        checked_total = 0
        supported_total = 0
        above_total = 0
        supported_candidates = 0
        all_supported_candidates = 0
        audit_rows: list[dict[str, object]] = []
        features: list[dict[str, object]] = []
        for candidate in candidates:
            checked, supported, above = _candidate_support(
                candidate,
                by_image,
                images,
                height_m=height,
                min_ratio=args.min_ratio,
                max_ratio=args.max_ratio,
            )
            checked_total += checked
            supported_total += supported
            above_total += above
            if supported > 0:
                supported_candidates += 1
            if checked > 0 and supported == checked:
                all_supported_candidates += 1
            if str(candidate["properties"]["candidate_id"]) in audit_by_id:
                audit_item = audit_by_id[str(candidate["properties"]["candidate_id"])]
                source = _source_detection(candidate, detections)
                image = images.get(str(source["image_id"])) if source is not None else None
                if source is not None and image is not None:
                    y = _f(source["ymax"])
                    ratio = ground_plane_ratio(
                        image,
                        y,
                        _f(source["depth_m"]),
                        camera_height_m=height,
                    )
                    consistent = ratio is not None and args.min_ratio <= ratio <= args.max_ratio
                    audit_rows.append(
                        {
                            "candidate_id": audit_item["candidate_id"],
                            "stratum": audit_item["stratum"],
                            "bottom_label": audit_item["bottom_label"],
                            "tree_mask_fraction": audit_item["tree_mask_fraction"],
                            "depth_ratio": None if ratio is None else round(ratio, 3),
                            "consistent": consistent,
                        }
                    )
            if height == 2.5 and supported > 0:
                feature = json.loads(json.dumps(candidate))
                feature["properties"]["ground_support"] = {
                    "supported_detections": supported,
                    "checked_detections": checked,
                    "camera_height_m": height,
                    "ratio_bounds": [args.min_ratio, args.max_ratio],
                    "note": "Screening gate only; level-camera assumption, not validated.",
                }
                features.append(feature)
        points = np.asarray(
            [
                _xy(
                    feature["geometry"]["coordinates"][0],
                    feature["geometry"]["coordinates"][1],
                    origin_lon,
                    origin_lat,
                )
                for feature in candidates
            ]
        )
        distances, _ = inventory_tree.query(points, k=1)
        supported_features = [
            feature
            for feature in candidates
            if _candidate_support(
                feature,
                by_image,
                images,
                height_m=height,
                min_ratio=args.min_ratio,
                max_ratio=args.max_ratio,
            )[1]
            > 0
        ]
        supported_distances = inventory_tree.query(
            np.asarray(
                [
                    _xy(
                        feature["geometry"]["coordinates"][0],
                        feature["geometry"]["coordinates"][1],
                        origin_lon,
                        origin_lat,
                    )
                    for feature in supported_features
                ]
            ),
            k=1,
        )[0]
        consistent_audit = [row for row in audit_rows if row["consistent"]]
        inconsistent_audit = [row for row in audit_rows if not row["consistent"]]

        def bottom_tree(rows: list[dict[str, object]]) -> dict[str, object]:
            total = len(rows)
            tree = sum(row["bottom_label"] == "tree" for row in rows)
            fractions = [_f(row["tree_mask_fraction"]) for row in rows]
            return {
                "count": total,
                "bottom_tree": tree,
                "bottom_tree_fraction": round(tree / total, 3) if total else None,
                "median_tree_mask_fraction": round(statistics.median(fractions), 3)
                if fractions
                else None,
            }

        results[str(height)] = {
            "camera_height_m": height,
            "checked_detections": checked_total,
            "supported_detections": supported_total,
            "above_horizon_detections": above_total,
            "supported_candidate_count": len(supported_features),
            "supported_candidate_fraction": round(len(supported_features) / len(candidates), 3),
            "supported_inventory_matched_count": int((supported_distances <= 8.0).sum()),
            "all_inventory_matched_count": int((distances <= 8.0).sum()),
            "all_consistent_candidate_count": all_supported_candidates,
            "audit_consistent": bottom_tree(consistent_audit),
            "audit_inconsistent": bottom_tree(inconsistent_audit),
        }
        if height == 2.5:
            args.sample_out.write_text(
                json.dumps({"type": "FeatureCollection", "features": features}, indent=2) + "\n",
                encoding="utf-8",
            )
    payload: dict[str, object] = {
        "schema_version": "fresh-urban-forest.street-tree-ground-gate.v1",
        "phase": "P71",
        "candidate_count": len(candidates),
        "detection_count": len(detections),
        "ratio_bounds": [args.min_ratio, args.max_ratio],
        "heights": list(args.heights),
        "results": results,
        "note": (
            "Level-camera sanity gate only. Camera pitch is unmodeled; the gate is not a "
            "field-validated detector or a precision/recall estimate."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Parameters
    ----------
    argv : list of str or None
        Arguments. ``None`` uses ``sys.argv``.

    Returns
    -------
    argparse.Namespace
        Parsed audit arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--detections", type=Path, required=True)
    parser.add_argument("--images-cache", type=Path, required=True)
    parser.add_argument("--images-dir", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sample-out", type=Path, required=True)
    parser.add_argument("--heights", type=float, nargs="+", default=[2.0, 2.5, 3.0])
    parser.add_argument("--min-ratio", type=float, default=0.5)
    parser.add_argument("--max-ratio", type=float, default=2.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the ground-plane gate audit.

    Parameters
    ----------
    argv : list of str or None
        Arguments. ``None`` uses ``sys.argv``.

    Returns
    -------
    int
        Zero on success.
    """
    run(parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
