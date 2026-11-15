#!/usr/bin/env python3
"""Citywide open street-level tree candidate sample for Vancouver.

This operator script extends the Commercial Drive pilot across a 1 km grid. It uses
KartaView public imagery and the P63/P64 open models. It is a screening sample, not a
citywide census.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import json
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform

from fresh_urban_forest.street_trees import (
    KartaViewClient,
    StreetDetection,
    StreetImage,
    candidates_geojson,
    detection_from_box,
    fuse_detections,
    match_inventory,
)
from street_tree_pilot import (
    DEPTH_MODEL,
    ONEFORMER_MODEL,
    _device,
    _load_inventory,
    _tree_components,
)

DEFAULT_FOV_DEG = 60.0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse citywide pilot arguments.

    Parameters
    ----------
    argv : list of str or None
        Arguments. ``None`` uses ``sys.argv``.

    Returns
    -------
    argparse.Namespace
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("data/processed/vancouver_2022"))
    parser.add_argument(
        "--images-dir",
        type=Path,
        default=Path("data/external/street_trees/city_images"),
    )
    parser.add_argument("--out", type=Path, default=Path("data/processed/street_trees_city"))
    parser.add_argument("--spacing", type=int, default=1000)
    parser.add_argument("--radius", type=int, default=500)
    parser.add_argument("--per-cell", type=int, default=6)
    parser.add_argument("--max-images", type=int, default=500)
    parser.add_argument("--min-area", type=int, default=1200)
    parser.add_argument("--fov", type=float, default=DEFAULT_FOV_DEG)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--max-workers", type=int, default=32)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument(
        "--include-dead-hosts",
        action="store_true",
        help="Include storage1 records whose blobs are normally missing.",
    )
    return parser.parse_args(argv)


def _grid_points(dataset: Path, spacing: int) -> tuple[tuple[float, float], ...]:
    """Return WGS84 centres of a projected grid inside the dataset boundary."""
    boundary = json.loads((dataset / "boundary.geojson").read_text(encoding="utf-8"))
    polygon = shape(boundary["features"][0]["geometry"])
    to_3157 = Transformer.from_crs("EPSG:4326", "EPSG:3157", always_xy=True)
    to_4326 = Transformer.from_crs("EPSG:3157", "EPSG:4326", always_xy=True)
    projected = transform(to_3157.transform, polygon)
    minx, miny, maxx, maxy = projected.bounds
    points: list[tuple[float, float]] = []
    x = minx + spacing / 2.0
    while x < maxx:
        y = miny + spacing / 2.0
        while y < maxy:
            if projected.contains(Point(x, y)):
                points.append(to_4326.transform(x, y))
            y += spacing
        x += spacing
    return tuple(points)


def _collect_images(
    client: KartaViewClient,
    points: tuple[tuple[float, float], ...],
    *,
    radius: int,
    scan_limit: int,
) -> dict[int, list[StreetImage]]:
    """Query each grid point and group unique images by grid cell."""
    by_cell: dict[int, list[StreetImage]] = defaultdict(list)
    seen: set[str] = set()
    started = time.time()
    for index, (lon, lat) in enumerate(points, 1):
        records: tuple[StreetImage, ...] = ()
        for attempt in range(3):
            try:
                records = client.images_near(
                    lon=lon,
                    lat=lat,
                    radius_m=radius,
                    limit=scan_limit,
                )
                break
            except Exception as error:  # pragma: no cover - network path
                status = getattr(getattr(error, "response", None), "status_code", None)
                if status == 429 and attempt < 2:
                    time.sleep(8.0 * (attempt + 1))
                    continue
                print(f"query {index}/{len(points)} failed: {error}", flush=True)
                break
        for image in records:
            if image.image_id in seen:
                continue
            seen.add(image.image_id)
            by_cell[index].append(image)
        if index % 10 == 0:
            print(
                f"cell {index}/{len(points)} unique={len(seen)} "
                f"elapsed={time.time() - started:.0f}s",
                flush=True,
            )
        time.sleep(0.6)
    return by_cell


def _storage_host(image: StreetImage) -> str:
    """Return the original storage host encoded in a KartaView CDN URL."""
    match = re.search(r"/pr:sharp/([^/?]+)", image.image_url)
    if match is None:
        return "unknown"
    encoded = match.group(1)
    try:
        source = base64.b64decode(encoded + "=" * ((4 - len(encoded) % 4) % 4)).decode()
    except Exception:
        return "unknown"
    return source.split("/")[2] if "://" in source else "unknown"


def _select_images(
    by_cell: dict[int, list[StreetImage]],
    *,
    per_cell: int,
    maximum: int,
) -> tuple[StreetImage, ...]:
    """Select evenly from cells, preferring storage hosts that still exist."""
    selected: list[StreetImage] = []
    cells = sorted(by_cell)
    for cell in cells:
        records = sorted(
            by_cell[cell],
            key=lambda image: (
                _storage_host(image) == "storage1.openstreetcam.org",
                _storage_host(image),
            ),
        )
        by_cell[cell] = records
    cursor = 0
    while len(selected) < maximum:
        added = False
        for cell in cells:
            records = by_cell[cell]
            if cursor < len(records) and cursor < per_cell:
                selected.append(records[cursor])
                added = True
                if len(selected) >= maximum:
                    break
        if not added:
            break
        cursor += 1
    return tuple(selected)


def _download_many(
    images: tuple[StreetImage, ...],
    directory: Path,
    *,
    max_workers: int,
) -> list[tuple[StreetImage, Image.Image]]:
    """Download and decode images concurrently, skipping failures."""
    directory.mkdir(parents=True, exist_ok=True)
    client = KartaViewClient()
    decoded: list[tuple[StreetImage, Image.Image]] = []

    def fetch(image: StreetImage) -> tuple[StreetImage, Image.Image]:
        path = directory / f"{image.image_id}.jpg"
        if not path.is_file() or path.stat().st_size == 0:
            path.write_bytes(client.image_bytes(image))
        with Image.open(path) as opened:
            rgb = opened.convert("RGB")
        return replace(image, width=rgb.width, height=rgb.height), rgb

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch, image): image for image in images}
        for completed, future in enumerate(as_completed(futures), 1):
            with contextlib.suppress(Exception):
                decoded.append(future.result())
            if completed % 50 == 0:
                print(
                    f"downloads {completed}/{len(images)} decoded={len(decoded)}",
                    flush=True,
                )
    return sorted(decoded, key=lambda item: item[0].image_id)


def _infer(
    images: tuple[StreetImage, ...],
    *,
    device: str,
    fov: float,
    min_area: int,
    images_dir: Path,
    max_workers: int,
    batch_size: int,
    detections_log: Path | None = None,
) -> tuple[tuple[StreetDetection, ...], int, int]:
    """Run the open segmentation and depth models over selected images."""
    from transformers import OneFormerForUniversalSegmentation, OneFormerProcessor, pipeline

    processor = OneFormerProcessor.from_pretrained(ONEFORMER_MODEL)
    segmenter = OneFormerForUniversalSegmentation.from_pretrained(ONEFORMER_MODEL).to(device)
    depth_pipe = pipeline(
        "depth-estimation",
        model=DEPTH_MODEL,
        device=0 if device == "cuda" else -1,
    )
    tree_id = next(
        (key for key, value in segmenter.config.id2label.items() if value == "tree"),
        None,
    )
    if tree_id is None:
        raise RuntimeError("segmentation model has no tree class")
    decoded = _download_many(images, images_dir, max_workers=max_workers)
    detections: list[StreetDetection] = []
    components = 0
    log_handle = detections_log.open("w", encoding="utf-8") if detections_log else None
    for start in range(0, len(decoded), batch_size):
        batch = decoded[start : start + batch_size]
        batch_detection_start = len(detections)
        rgb_images = [rgb for _image, rgb in batch]
        inputs = processor(
            images=rgb_images,
            task_inputs=["semantic"] * len(rgb_images),
            return_tensors="pt",
        ).to(device)
        with torch.no_grad():
            outputs = segmenter(**inputs)
        semantic_maps = processor.post_process_semantic_segmentation(
            outputs,
            target_sizes=[rgb.size[::-1] for rgb in rgb_images],
        )
        depth_results = depth_pipe(rgb_images)
        for (image, rgb), semantic, depth_result in zip(
            batch,
            semantic_maps,
            depth_results,
            strict=True,
        ):
            image = StreetImage(
                provider=image.provider,
                image_id=image.image_id,
                lon=image.lon,
                lat=image.lat,
                heading_deg=image.heading_deg,
                width=rgb.width,
                height=rgb.height,
                captured_at=image.captured_at,
                image_url=image.image_url,
                license=image.license,
                attribution=image.attribution,
                horizontal_fov_deg=fov,
                fov_source="assumed_default",
            )
            boxes = _tree_components(rgb, semantic.cpu().numpy() == tree_id, min_area=min_area)
            components += len(boxes)
            depth = np.squeeze(depth_result["predicted_depth"].detach().cpu().numpy())
            if depth.ndim != 2:
                continue
            if depth.shape != (rgb.height, rgb.width):
                depth = np.asarray(
                    Image.fromarray(depth.astype(np.float32), mode="F").resize(
                        rgb.size, Image.Resampling.BILINEAR
                    )
                )
            for box in boxes:
                xmin, ymin, xmax, ymax = box
                lower = max(ymin, int(ymax - 0.25 * (ymax - ymin)))
                crop = depth[int(lower) : int(ymax) + 1, int(xmin) : int(xmax) + 1]
                values = crop[np.isfinite(crop) & (crop > 0)]
                if values.size == 0:
                    continue
                area = max((xmax - xmin) * (ymax - ymin), 1.0)
                score = min(0.95, 0.35 + 0.6 * min(area / 20_000.0, 1.0))
                detections.append(
                    detection_from_box(
                        image,
                        box,
                        score=score,
                        depth_m=float(np.median(values)),
                    )
                )
        if log_handle is not None:
            for detection in detections[batch_detection_start:]:
                log_handle.write(json.dumps(asdict(detection)) + "\n")
            log_handle.flush()
        print(
            f"inferred {min(start + len(batch), len(decoded))}/{len(decoded)} "
            f"components={components} detections={len(detections)}",
            flush=True,
        )
    if log_handle is not None:
        log_handle.close()
    return tuple(detections), components, len(decoded)


def run(args: argparse.Namespace) -> dict[str, object]:
    """Run the citywide sample and write outputs.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments.

    Returns
    -------
    dict[str, object]
        Citywide summary.
    """
    args.out.mkdir(parents=True, exist_ok=True)
    points = _grid_points(args.dataset, args.spacing)
    print(f"grid points: {len(points)}", flush=True)
    client = KartaViewClient()
    by_cell = _collect_images(
        client,
        points,
        radius=args.radius,
        scan_limit=100,
    )
    if not args.include_dead_hosts:
        for cell in list(by_cell):
            by_cell[cell] = [
                image
                for image in by_cell[cell]
                if _storage_host(image) != "storage1.openstreetcam.org"
            ]
    selected = _select_images(by_cell, per_cell=args.per_cell, maximum=args.max_images)
    host_counts = Counter(_storage_host(image) for image in selected)
    print(
        f"selected images: {len(selected)} across {len(by_cell)} cells; hosts={dict(host_counts)}",
        flush=True,
    )
    if not selected:
        raise RuntimeError("no KartaView images selected")
    device = _device(args.device)
    detections, components, decoded_count = _infer(
        selected,
        device=device,
        fov=args.fov,
        min_area=args.min_area,
        images_dir=args.images_dir,
        max_workers=args.max_workers,
        batch_size=args.batch_size,
        detections_log=args.out / "street_tree_detections.jsonl",
    )
    (args.out / "street_tree_detections.json").write_text(
        json.dumps([asdict(detection) for detection in detections], indent=2) + "\n",
        encoding="utf-8",
    )
    candidates = fuse_detections(detections, radius_m=7.0)
    inventory = _load_inventory(args.dataset)
    summary = match_inventory(candidates, inventory, tolerance_m=8.0) if inventory else None
    (args.out / "street_tree_candidates_citywide.geojson").write_text(
        json.dumps(candidates_geojson(candidates), indent=2) + "\n",
        encoding="utf-8",
    )
    payload: dict[str, object] = {
        "schema_version": "fresh-urban-forest.street-tree-pilot.v1",
        "extent": "vancouver_citywide_sample",
        "method": "OneFormer semantic tree mask + distance-peak split + ZoeDepth depth",
        "models": {
            "segmentation": ONEFORMER_MODEL,
            "segmentation_license": "MIT",
            "depth": DEPTH_MODEL,
            "depth_license": "MIT",
        },
        "provider": "kartaview",
        "provider_license": "CC BY-SA 4.0",
        "provider_attribution": "© Grab and KartaView contributors",
        "grid": {"spacing_m": args.spacing, "radius_m": args.radius, "cells": len(points)},
        "image_count": decoded_count,
        "detection_cache": "street_tree_detections.json",
        "selected_image_count": len(selected),
        "selected_storage_hosts": dict(host_counts),
        "downloaded_image_count": decoded_count,
        "component_count": components,
        "detection_count": len(detections),
        "candidate_count": len(candidates),
        "inventory_match_tolerance_m": 8.0,
        "inventory_matched_count": summary.matched_count if summary else 0,
        "inventory_median_distance_m": summary.median_distance_m if summary else None,
        "fov_source": "assumed_default",
        "assumed_horizontal_fov_deg": args.fov,
        "live_hosts_only": not args.include_dead_hosts,
        "caveats": [
            "KartaView imagery is CC BY-SA 4.0 and must be attributed.",
            "KartaView often omits camera FOV; 60° is assumed.",
            "Coverage is a sampled road-network grid, not a complete image census.",
            "Imagery is predominantly 2016-2018; inventory is current.",
            "Public tree inventory is incomplete for private trees; "
            "unmatched candidates are not false positives.",
            "Candidates are screening estimates, not field-validated tree locations.",
            "The layer is separate from LiDAR off-inventory and official inventory.",
        ],
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (args.out / "street_tree_candidates_citywide.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2), flush=True)
    return payload


def main(argv: list[str] | None = None) -> int:
    """Run the citywide sample.

    Parameters
    ----------
    argv : list of str or None
        Arguments.

    Returns
    -------
    int
        Zero on success.
    """
    run(parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
