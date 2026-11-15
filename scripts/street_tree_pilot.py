#!/usr/bin/env python3
"""Pilot: open street-level tree candidates for a Vancouver corridor.

This is an operator script, not a default application path. It uses optional ML
dependencies and keeps street-level candidates separate from the LiDAR off-inventory layer.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from scipy import ndimage
from skimage.feature import peak_local_max
from skimage.segmentation import watershed
from transformers import (
    OneFormerForUniversalSegmentation,
    OneFormerProcessor,
    pipeline,
)

from fresh_urban_forest.street_trees import (
    KartaViewClient,
    StreetDetection,
    StreetImage,
    candidates_geojson,
    detection_from_box,
    fuse_detections,
    match_inventory,
)

ONEFORMER_MODEL = "shi-labs/oneformer_ade20k_swin_tiny"
DEPTH_MODEL = "Intel/zoedepth-nyu-kitti"
DEFAULT_FOV_DEG = 60.0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse pilot arguments.

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
    parser.add_argument("--lon", type=float, default=-123.0700)
    parser.add_argument("--lat", type=float, default=49.2700)
    parser.add_argument("--radius", type=int, default=500)
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--min-area", type=int, default=1200)
    parser.add_argument("--fov", type=float, default=DEFAULT_FOV_DEG)
    parser.add_argument("--dataset", type=Path, default=Path("data/processed/vancouver_2022"))
    parser.add_argument("--images-dir", type=Path, default=Path("data/external/street_trees"))
    parser.add_argument("--out", type=Path, default=Path("data/processed/street_trees_pilot"))
    parser.add_argument("--device", default="auto")
    return parser.parse_args(argv)


def _device(value: str) -> str:
    """Resolve the device argument."""
    if value != "auto":
        return value
    return "cuda" if torch.cuda.is_available() else "cpu"


def _download_images(
    client: KartaViewClient,
    images: tuple[StreetImage, ...],
    directory: Path,
    *,
    target_count: int | None = None,
) -> list[tuple[StreetImage, Image.Image]]:
    """Download and decode available images."""
    directory.mkdir(parents=True, exist_ok=True)
    result: list[tuple[StreetImage, Image.Image]] = []
    for index, image in enumerate(images, 1):
        if target_count is not None and len(result) >= target_count:
            break
        path = directory / f"{image.image_id}.jpg"
        try:
            if not path.is_file() or path.stat().st_size == 0:
                path.write_bytes(client.image_bytes(image))
            with Image.open(path) as opened:
                rgb = opened.convert("RGB")
            result.append((replace(image, width=rgb.width, height=rgb.height), rgb))
        except Exception as error:  # pragma: no cover - network path
            print(f"image {index}/{len(images)} failed: {error}", flush=True)
    return result


def _tree_components(
    image: Image.Image,
    tree_mask: np.ndarray,
    *,
    min_area: int,
) -> tuple[tuple[float, float, float, float], ...]:
    """Split a semantic tree mask into instance-like components."""
    binary = tree_mask.astype(bool)
    distance = ndimage.distance_transform_edt(binary)
    peaks = peak_local_max(distance, min_distance=22, threshold_abs=2.0, labels=binary)  # type: ignore[no-untyped-call]  # skimage has no stubs
    markers = np.zeros(binary.shape, dtype=np.int32)
    if len(peaks) > 0:
        for index, (row, col) in enumerate(peaks, 1):
            markers[row, col] = index
        labels = watershed(-distance, markers, mask=binary)  # type: ignore[no-untyped-call]  # skimage has no stubs
    else:
        labels, _ = ndimage.label(binary)
    boxes: list[tuple[float, float, float, float]] = []
    for label in np.unique(labels):
        if label == 0:
            continue
        rows, cols = np.where(labels == label)
        if len(rows) < min_area:
            continue
        ymin, ymax = int(rows.min()), int(rows.max())
        xmin, xmax = int(cols.min()), int(cols.max())
        if ymax - ymin < 20 or xmax - xmin < 20:
            continue
        boxes.append((float(xmin), float(ymin), float(xmax), float(ymax)))
    return tuple(boxes)


def _load_inventory(dataset: Path) -> tuple[tuple[float, float, str], ...]:
    """Load public tree points for matching."""
    path = dataset / "map_trees.json.gz"
    if not path.is_file():
        return ()
    import gzip

    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    points: list[tuple[float, float, str]] = []
    for feature in payload.get("features", []):
        geometry = feature.get("geometry", {})
        coordinates = geometry.get("coordinates", [])
        properties = feature.get("properties", {})
        if len(coordinates) >= 2 and len(points) < 250_000:
            points.append(
                (
                    float(coordinates[0]),
                    float(coordinates[1]),
                    str(properties.get("tree_id", "")),
                )
            )
    return tuple(points)


def run(args: argparse.Namespace) -> dict[str, object]:
    """Run the corridor pilot and write outputs.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed pilot arguments.

    Returns
    -------
    dict[str, object]
        Pilot summary written next to the candidates.
    """
    device = _device(args.device)
    print(f"device={device}", flush=True)
    client = KartaViewClient()
    scan_limit = min(max(args.limit * 12, args.limit), 100)
    images = client.images_near(
        lon=args.lon,
        lat=args.lat,
        radius_m=args.radius,
        limit=scan_limit,
    )
    print(f"images: {len(images)}", flush=True)
    decoded = _download_images(client, images, args.images_dir, target_count=args.limit)
    print(f"decoded: {len(decoded)}", flush=True)
    if not decoded:
        raise RuntimeError("no street-level images could be downloaded")

    processor = OneFormerProcessor.from_pretrained(ONEFORMER_MODEL)
    segmenter = OneFormerForUniversalSegmentation.from_pretrained(ONEFORMER_MODEL).to(device)
    depth_pipe = pipeline(
        "depth-estimation", model=DEPTH_MODEL, device=0 if device == "cuda" else -1
    )
    tree_id = next(
        (key for key, value in segmenter.config.id2label.items() if value == "tree"),
        None,
    )
    if tree_id is None:
        raise RuntimeError("segmentation model has no tree class")

    detections: list[StreetDetection] = []
    components_total = 0
    for index, (image, rgb) in enumerate(decoded, 1):
        inputs = processor(images=rgb, task_inputs=["semantic"], return_tensors="pt").to(device)
        with torch.no_grad():
            outputs = segmenter(**inputs)
        semantic = (
            processor.post_process_semantic_segmentation(
                outputs,
                target_sizes=[rgb.size[::-1]],
            )[0]
            .cpu()
            .numpy()
        )
        tree_mask = semantic == tree_id
        boxes = _tree_components(rgb, tree_mask, min_area=args.min_area)
        components_total += len(boxes)
        depth_result = depth_pipe(rgb)
        depth_tensor = depth_result["predicted_depth"]
        depth = np.squeeze(depth_tensor.detach().cpu().numpy())
        if depth.ndim != 2:
            raise RuntimeError(f"unexpected depth shape: {depth.shape}")
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
            depth_m = float(np.median(values))
            area = max((xmax - xmin) * (ymax - ymin), 1.0)
            score = min(0.95, 0.35 + 0.6 * min(area / 20_000.0, 1.0))
            detections.append(
                detection_from_box(
                    image,
                    box,
                    score=score,
                    depth_m=depth_m,
                    label="tree",
                )
            )
        print(
            f"image {index}/{len(decoded)} id={image.image_id} components={len(boxes)} "
            f"detections={len(detections)}",
            flush=True,
        )

    candidates = fuse_detections(tuple(detections), radius_m=7.0)
    inventory = _load_inventory(args.dataset)
    summary = match_inventory(candidates, inventory, tolerance_m=8.0) if inventory else None
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "street_tree_candidates.geojson").write_text(
        json.dumps(candidates_geojson(candidates), indent=2) + "\n",
        encoding="utf-8",
    )
    payload: dict[str, object] = {
        "schema_version": "fresh-urban-forest.street-tree-pilot.v1",
        "method": "OneFormer ADE20K semantic tree mask + watershed split + ZoeDepth metric depth",
        "models": {
            "segmentation": ONEFORMER_MODEL,
            "segmentation_license": "MIT",
            "depth": DEPTH_MODEL,
            "depth_license": "MIT",
        },
        "provider": "kartaview",
        "provider_license": "CC BY-SA 4.0",
        "provider_attribution": "© Grab and KartaView contributors",
        "query": {"lon": args.lon, "lat": args.lat, "radius_m": args.radius},
        "assumed_horizontal_fov_deg": args.fov,
        "fov_source": "assumed_default",
        "image_count": len(decoded),
        "component_count": components_total,
        "detection_count": len(detections),
        "candidate_count": len(candidates),
        "inventory_match_tolerance_m": 8.0,
        "inventory_matched_count": summary.matched_count if summary else 0,
        "inventory_median_distance_m": summary.median_distance_m if summary else None,
        "caveats": [
            "KartaView imagery is CC BY-SA 4.0 and must be attributed.",
            "KartaView often omits camera FOV; a documented default FOV is used.",
            "The public tree inventory is incomplete for private trees; "
            "unmatched candidates are not false positives.",
            "Candidate positions are screening estimates, not field-validated tree locations.",
            "This layer is separate from the LiDAR off-inventory layer and is not merged with it.",
        ],
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (args.out / "street_tree_pilot.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2), flush=True)
    return payload


def main(argv: list[str] | None = None) -> int:
    """Run the pilot command.

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
