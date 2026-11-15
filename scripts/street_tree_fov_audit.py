"""Audit FOV metadata and reproject cached street-tree detections.

This operator script does not run the segmentation or depth models. It reloads cached
detections, rebuilds the selected KartaView image metadata, and compares 50°, 60°, and
70° horizontal-FOV assumptions. It is a sensitivity audit, not a calibration claim.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from dataclasses import asdict, replace
from pathlib import Path

from PIL import Image
from scipy.spatial import cKDTree

from fresh_urban_forest.street_trees import (
    KartaViewClient,
    StreetDetection,
    StreetImage,
    fuse_detections,
    match_inventory,
    project_pixel,
)
from street_tree_city import (
    _collect_images,
    _grid_points,
    _storage_host,
)
from street_tree_city import (
    _select_images as _select_cell_images,
)
from street_tree_pilot import _load_inventory


def _local_xy(lon: float, lat: float, origin_lon: float, origin_lat: float) -> tuple[float, float]:
    """Return local east/north metres from an origin."""
    east = (lon - origin_lon) * 111_320.0 * math.cos(math.radians(origin_lat))
    north = (lat - origin_lat) * 110_540.0
    return east, north


def _distance_m(first_lon: float, first_lat: float, second_lon: float, second_lat: float) -> float:
    east, north = _local_xy(second_lon, second_lat, first_lon, first_lat)
    return math.hypot(east, north)


def _quantiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)

    def at(fraction: float) -> float:
        index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
        return round(ordered[index], 3)

    return {
        "min": round(ordered[0], 3),
        "median": round(statistics.median(ordered), 3),
        "p90": at(0.90),
        "p95": at(0.95),
        "p99": at(0.99),
        "max": round(ordered[-1], 3),
    }


def _load_or_select_images(
    dataset: Path,
    *,
    cache_path: Path,
    spacing: int,
    radius: int,
    per_cell: int,
    maximum: int,
) -> tuple[StreetImage, ...]:
    """Load selected metadata from cache or query the public provider."""
    if cache_path.is_file():
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        images = tuple(StreetImage(**item) for item in payload)
        print(f"loaded {len(images)} cached image records from {cache_path}", flush=True)
        return images
    points = _grid_points(dataset, spacing)
    client = KartaViewClient()
    by_cell = _collect_images(client, points, radius=radius, scan_limit=100)
    for cell in list(by_cell):
        by_cell[cell] = [
            image for image in by_cell[cell] if _storage_host(image) != "storage1.openstreetcam.org"
        ]
    selected = _select_cell_images(
        by_cell,
        per_cell=per_cell,
        maximum=maximum,
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps([asdict(image) for image in selected], indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"cached {len(selected)} selected image records to {cache_path}", flush=True)
    return selected


def _apply_actual_image_sizes(
    images: tuple[StreetImage, ...],
    images_dir: Path,
) -> tuple[tuple[StreetImage, ...], int]:
    """Use decoded image dimensions; provider metadata often disagrees."""
    adjusted: list[StreetImage] = []
    overridden = 0
    for image in images:
        path = images_dir / f"{image.image_id}.jpg"
        if not path.is_file():
            adjusted.append(image)
            continue
        with Image.open(path) as opened:
            if (opened.width, opened.height) != (image.width, image.height):
                image = replace(image, width=opened.width, height=opened.height)
                overridden += 1
        adjusted.append(image)
    return tuple(adjusted), overridden


def _reproject(
    detections: tuple[StreetDetection, ...],
    images: dict[str, StreetImage],
    *,
    fov_deg: float,
    heading_offset_deg: float = 0.0,
) -> tuple[StreetDetection, ...]:
    projected: list[StreetDetection] = []
    for detection in detections:
        image = images.get(detection.image_id)
        if image is None:
            projected.append(detection)
            continue
        adjusted = replace(
            image,
            horizontal_fov_deg=fov_deg,
            fov_source="audit",
            heading_deg=(image.heading_deg + heading_offset_deg) % 360.0,
        )
        lon, lat = project_pixel(
            adjusted,
            (detection.xmin + detection.xmax) / 2.0,
            detection.depth_m,
        )
        projected.append(replace(detection, lon=lon, lat=lat))
    return tuple(projected)


def run(args: argparse.Namespace) -> dict[str, object]:
    """Run the FOV metadata and projection sensitivity audit.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed audit arguments.

    Returns
    -------
    dict[str, object]
        Audit payload written to the output path.
    """
    dataset = args.dataset
    detections = tuple(
        StreetDetection(**item) for item in json.loads(args.detections.read_text(encoding="utf-8"))
    )
    selected = _load_or_select_images(
        dataset,
        cache_path=args.images_cache,
        spacing=args.spacing,
        radius=args.radius,
        per_cell=args.per_cell,
        maximum=args.max_images,
    )
    selected, size_overrides = _apply_actual_image_sizes(selected, args.images_dir)
    images = {image.image_id: image for image in selected}
    inventory = _load_inventory(dataset)
    model_fov = [image.horizontal_fov_deg for image in selected if image.fov_source == "provider"]
    heading_values = [image.heading_deg % 360.0 for image in selected]
    depth_values = [detection.depth_m for detection in detections if detection.depth_m > 0]
    baseline = detections
    baseline_candidates = fuse_detections(
        baseline,
        radius_m=args.fusion_radius,
        max_spread_m=args.max_spread,
    )
    baseline_match = match_inventory(baseline_candidates, inventory, tolerance_m=8.0)
    results: dict[str, object] = {}
    for fov in args.fovs:
        started = time.time()
        projected = _reproject(baseline, images, fov_deg=fov)
        displacements = [
            _distance_m(first.lon, first.lat, second.lon, second.lat)
            for first, second in zip(baseline, projected, strict=True)
        ]
        candidates = fuse_detections(
            projected,
            radius_m=args.fusion_radius,
            max_spread_m=args.max_spread,
        )
        match = match_inventory(candidates, inventory, tolerance_m=8.0)
        baseline_points = [(item.lon, item.lat) for item in baseline_candidates]
        candidate_points = [(item.lon, item.lat) for item in candidates]
        origin_lon, origin_lat = baseline_points[0]
        baseline_xy = [_local_xy(lon, lat, origin_lon, origin_lat) for lon, lat in baseline_points]
        candidate_xy = [
            _local_xy(lon, lat, origin_lon, origin_lat) for lon, lat in candidate_points
        ]
        tree = cKDTree(candidate_xy)
        distances_5, _ = tree.query(baseline_xy, k=1, distance_upper_bound=5.0)
        distances_10, _ = tree.query(baseline_xy, k=1, distance_upper_bound=10.0)
        results[str(fov)] = {
            "fov_deg": fov,
            "candidate_count": len(candidates),
            "inventory_matched_count": match.matched_count,
            "inventory_median_distance_m": match.median_distance_m,
            "detection_displacement_m": _quantiles(displacements),
            "baseline_candidates_with_variant_within_5m": int((distances_5 <= 5.0).sum()),
            "baseline_candidates_with_variant_within_10m": int((distances_10 <= 10.0).sum()),
            "elapsed_seconds": round(time.time() - started, 1),
        }
        print(json.dumps(results[str(fov)], indent=2), flush=True)
    heading_results: dict[str, object] = {}
    for heading_offset in args.heading_offsets:
        projected = _reproject(
            baseline,
            images,
            fov_deg=60.0,
            heading_offset_deg=heading_offset,
        )
        displacements = [
            _distance_m(first.lon, first.lat, second.lon, second.lat)
            for first, second in zip(baseline, projected, strict=True)
        ]
        candidates = fuse_detections(
            projected,
            radius_m=args.fusion_radius,
            max_spread_m=args.max_spread,
        )
        match = match_inventory(candidates, inventory, tolerance_m=8.0)
        baseline_points = [(item.lon, item.lat) for item in baseline_candidates]
        candidate_points = [(item.lon, item.lat) for item in candidates]
        origin_lon, origin_lat = baseline_points[0]
        baseline_xy = [_local_xy(lon, lat, origin_lon, origin_lat) for lon, lat in baseline_points]
        candidate_xy = [
            _local_xy(lon, lat, origin_lon, origin_lat) for lon, lat in candidate_points
        ]
        tree = cKDTree(candidate_xy)
        distances_5, _ = tree.query(baseline_xy, k=1, distance_upper_bound=5.0)
        distances_10, _ = tree.query(baseline_xy, k=1, distance_upper_bound=10.0)
        heading_results[str(heading_offset)] = {
            "heading_offset_deg": heading_offset,
            "candidate_count": len(candidates),
            "inventory_matched_count": match.matched_count,
            "inventory_median_distance_m": match.median_distance_m,
            "detection_displacement_m": _quantiles(displacements),
            "baseline_candidates_with_variant_within_5m": int((distances_5 <= 5.0).sum()),
            "baseline_candidates_with_variant_within_10m": int((distances_10 <= 10.0).sum()),
        }
    payload: dict[str, object] = {
        "schema_version": "fresh-urban-forest.street-tree-fov-audit.v1",
        "phase": "P68",
        "detection_count": len(detections),
        "selected_metadata_image_count": len(images),
        "detection_unique_image_count": len({detection.image_id for detection in detections}),
        "missing_metadata_image_count": len(
            {detection.image_id for detection in detections if detection.image_id not in images}
        ),
        "missing_metadata_detection_count": sum(
            detection.image_id not in images for detection in detections
        ),
        "selected_image_count": len(selected),
        "image_size_overrides": size_overrides,
        "provider_fov_image_count": len(model_fov),
        "provider_fov_values": sorted(set(model_fov)),
        "assumed_fov_image_count": sum(image.fov_source != "provider" for image in selected),
        "heading_distinct_values": len({round(value, 3) for value in heading_values}),
        "heading_min": min(heading_values),
        "heading_max": max(heading_values),
        "depth_m": _quantiles(depth_values),
        "baseline": {
            "candidate_count": len(baseline_candidates),
            "inventory_matched_count": baseline_match.matched_count,
            "inventory_median_distance_m": baseline_match.median_distance_m,
        },
        "fov_results": results,
        "heading_results": heading_results,
        "note": (
            "Sensitivity audit only. FOV and camera pose are not calibrated; "
            "no field validation or precision/recall claim."
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
    parser.add_argument("--detections", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--images-cache", type=Path, required=True)
    parser.add_argument("--images-dir", type=Path, required=True)
    parser.add_argument("--spacing", type=int, default=1000)
    parser.add_argument("--radius", type=int, default=500)
    parser.add_argument("--per-cell", type=int, default=100)
    parser.add_argument("--max-images", type=int, default=7000)
    parser.add_argument("--fusion-radius", type=float, default=7.0)
    parser.add_argument("--max-spread", type=float, default=10.0)
    parser.add_argument("--fovs", type=float, nargs="+", default=[50.0, 60.0, 70.0])
    parser.add_argument("--heading-offsets", type=float, nargs="+", default=[-5.0, 5.0])
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the audit command.

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
