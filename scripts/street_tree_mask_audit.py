"""Audit street-tree detector boxes with the existing semantic model.

The script samples 200 candidates across inventory-match and view-count strata, re-runs
OneFormer on their source images, and measures tree-mask coverage and the semantic class at
the box bottom centre. It also writes contact sheets for visual review. This is a descriptive
screening audit, not a precision or recall estimate.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.spatial import cKDTree

from street_tree_pilot import ONEFORMER_MODEL, _device, _load_inventory


@dataclass(frozen=True, slots=True)
class AuditCandidate:
    """One sampled candidate and its source detection."""

    candidate_id: str
    view_count: int
    score: float
    uncertainty_m: float
    lon: float
    lat: float
    nearest_inventory_m: float
    image_id: str
    box: tuple[float, float, float, float]
    depth_m: float
    stratum: str


def _f(value: object) -> float:
    """Convert a JSON scalar to float."""
    return float(cast("str | int | float", value))


def _xy(lon: float, lat: float, origin_lon: float, origin_lat: float) -> tuple[float, float]:
    return (
        (lon - origin_lon) * 111_320.0 * math.cos(math.radians(origin_lat)),
        (lat - origin_lat) * 110_540.0,
    )


def _choose(seq: list[AuditCandidate], count: int) -> list[AuditCandidate]:
    ordered = sorted(seq, key=lambda item: item.candidate_id)
    if len(ordered) <= count:
        return ordered
    step = len(ordered) / count
    return [ordered[min(len(ordered) - 1, int(index * step))] for index in range(count)]


def _sample(
    candidates_path: Path,
    detections_path: Path,
    dataset: Path,
    *,
    per_stratum: int,
) -> tuple[list[AuditCandidate], dict[str, int]]:
    candidates = json.loads(candidates_path.read_text(encoding="utf-8"))["features"]
    detections = json.loads(detections_path.read_text(encoding="utf-8"))
    by_image: dict[str, list[dict[str, object]]] = {}
    for detection in detections:
        by_image.setdefault(str(detection["image_id"]), []).append(detection)
    inventory = _load_inventory(dataset)
    origin_lon, origin_lat = inventory[0][0], inventory[0][1]
    inventory_xy = np.asarray(
        [_xy(lon, lat, origin_lon, origin_lat) for lon, lat, _tree_id in inventory]
    )
    tree = cKDTree(inventory_xy)
    strata: dict[str, list[AuditCandidate]] = {
        "single_matched": [],
        "single_unmatched": [],
        "multi_matched": [],
        "multi_unmatched": [],
    }
    for feature in candidates:
        properties = feature["properties"]
        lon, lat = feature["geometry"]["coordinates"]
        distance, _ = tree.query(_xy(lon, lat, origin_lon, origin_lat), k=1)
        best: dict[str, object] | None = None
        best_distance = float("inf")
        for image_id in properties["image_ids"]:
            for detection in by_image.get(image_id, []):
                dx, dy = _xy(
                    _f(detection["lon"]),
                    _f(detection["lat"]),
                    lon,
                    lat,
                )
                candidate_distance = math.hypot(dx, dy)
                if candidate_distance < best_distance:
                    best = detection
                    best_distance = candidate_distance
        if best is None:
            continue
        view_count = int(properties["view_count"])
        matched = float(distance) <= 8.0
        stratum = ("multi" if view_count >= 2 else "single") + (
            "_matched" if matched else "_unmatched"
        )
        strata[stratum].append(
            AuditCandidate(
                candidate_id=str(properties["candidate_id"]),
                view_count=view_count,
                score=_f(properties["score"]),
                uncertainty_m=_f(properties["positional_uncertainty_m"]),
                lon=float(lon),
                lat=float(lat),
                nearest_inventory_m=float(distance),
                image_id=str(best["image_id"]),
                box=(
                    _f(best["xmin"]),
                    _f(best["ymin"]),
                    _f(best["xmax"]),
                    _f(best["ymax"]),
                ),
                depth_m=_f(best["depth_m"]),
                stratum=stratum,
            )
        )
    selected: list[AuditCandidate] = []
    for name in strata:
        selected.extend(_choose(strata[name], per_stratum))
    counts = {name: len(_choose(values, per_stratum)) for name, values in strata.items()}
    return selected, counts


def _contact_sheets(
    samples: list[AuditCandidate],
    images_dir: Path,
    output_dir: Path,
) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default()
    thumb_w, thumb_h, label_h = 300, 190, 45
    cols, rows = 5, 10
    paths: list[str] = []
    for page in range(math.ceil(len(samples) / (cols * rows))):
        subset = samples[page * cols * rows : (page + 1) * cols * rows]
        sheet = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + label_h)), (247, 245, 239))
        draw = ImageDraw.Draw(sheet)
        for index, sample in enumerate(subset):
            path = images_dir / f"{sample.image_id}.jpg"
            if not path.is_file():
                continue
            with Image.open(path) as opened:
                image = opened.convert("RGB")
            xmin, ymin, xmax, ymax = sample.box
            pad = 70
            left = max(0, int(xmin - pad))
            top = max(0, int(ymin - pad))
            right = min(image.width, int(xmax + pad))
            bottom = min(image.height, int(ymax + pad))
            crop = image.crop((left, top, right, bottom)).resize((thumb_w, thumb_h))
            sx = thumb_w / max(right - left, 1)
            sy = thumb_h / max(bottom - top, 1)
            crop_draw = ImageDraw.Draw(crop)
            crop_draw.rectangle(
                ((xmin - left) * sx, (ymin - top) * sy, (xmax - left) * sx, (ymax - top) * sy),
                outline=(220, 30, 30),
                width=3,
            )
            x = (index % cols) * thumb_w
            y = (index // cols) * (thumb_h + label_h)
            sheet.paste(crop, (x, y))
            draw.text(
                (x + 4, y + thumb_h + 2),
                f"{sample.candidate_id}  {sample.stratum}",
                fill=(20, 30, 25),
                font=font,
            )
            draw.text(
                (x + 4, y + thumb_h + 16),
                f"views={sample.view_count} inv={sample.nearest_inventory_m:.1f}m",
                fill=(70, 80, 72),
                font=font,
            )
            draw.text(
                (x + 4, y + thumb_h + 30),
                f"depth={sample.depth_m:.1f}m unc=±{sample.uncertainty_m:.1f}m",
                fill=(70, 80, 72),
                font=font,
            )
        path = output_dir / f"p69-audit-sheet-{page + 1}.png"
        sheet.save(path)
        paths.append(str(path))
    return paths


def run(args: argparse.Namespace) -> dict[str, object]:
    """Run the stratified mask audit.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed audit arguments.

    Returns
    -------
    dict[str, object]
        Audit payload written to disk.
    """
    import torch
    from transformers import OneFormerForUniversalSegmentation, OneFormerProcessor

    samples, stratum_counts = _sample(
        args.candidates,
        args.detections,
        args.dataset,
        per_stratum=args.per_stratum,
    )
    processor = OneFormerProcessor.from_pretrained(ONEFORMER_MODEL)
    segmenter = OneFormerForUniversalSegmentation.from_pretrained(ONEFORMER_MODEL).to(
        _device(args.device)
    )
    tree_id = next(
        (key for key, value in segmenter.config.id2label.items() if value == "tree"),
        None,
    )
    if tree_id is None:
        raise RuntimeError("segmentation model has no tree class")
    labels = segmenter.config.id2label
    by_image: dict[str, list[AuditCandidate]] = {}
    for sample in samples:
        by_image.setdefault(sample.image_id, []).append(sample)
    records: list[dict[str, object]] = []
    image_ids = sorted(by_image)
    for start in range(0, len(image_ids), args.batch_size):
        batch_ids = image_ids[start : start + args.batch_size]
        rgb_images: list[Image.Image] = []
        kept_ids: list[str] = []
        for image_id in batch_ids:
            path = args.images_dir / f"{image_id}.jpg"
            if not path.is_file():
                continue
            with Image.open(path) as opened:
                rgb_images.append(opened.convert("RGB"))
            kept_ids.append(image_id)
        if not rgb_images:
            continue
        inputs = processor(
            images=rgb_images,
            task_inputs=["semantic"] * len(rgb_images),
            return_tensors="pt",
        ).to(_device(args.device))
        with torch.no_grad(), np.errstate(all="ignore"):
            outputs = segmenter(**inputs)
            semantic_maps = processor.post_process_semantic_segmentation(
                outputs,
                target_sizes=[rgb.size[::-1] for rgb in rgb_images],
            )
        for image_id, rgb, semantic_tensor in zip(kept_ids, rgb_images, semantic_maps, strict=True):
            semantic = semantic_tensor.cpu().numpy()
            for sample in by_image[image_id]:
                xmin, ymin, xmax, ymax = sample.box
                left = max(0, min(rgb.width - 1, round(xmin)))
                right = max(left + 1, min(rgb.width, round(xmax)))
                top = max(0, min(rgb.height - 1, round(ymin)))
                bottom = max(top + 1, min(rgb.height, round(ymax)))
                box_labels = semantic[top:bottom, left:right]
                total = max(int(box_labels.size), 1)
                tree_fraction = float((box_labels == tree_id).sum() / total)
                values, counts = np.unique(box_labels, return_counts=True)
                fractions = {
                    str(labels[int(value)]): round(float(count / total), 3)
                    for value, count in sorted(
                        zip(values, counts, strict=True),
                        key=lambda pair: int(pair[1]),
                        reverse=True,
                    )[:5]
                }
                bottom_x = min(rgb.width - 1, max(0, round((xmin + xmax) / 2.0)))
                bottom_y = min(rgb.height - 1, max(0, round(ymax)))
                bottom_label = str(labels[int(semantic[bottom_y, bottom_x])])
                records.append(
                    {
                        "candidate_id": sample.candidate_id,
                        "stratum": sample.stratum,
                        "image_id": sample.image_id,
                        "view_count": sample.view_count,
                        "score": sample.score,
                        "uncertainty_m": sample.uncertainty_m,
                        "nearest_inventory_m": round(sample.nearest_inventory_m, 2),
                        "depth_m": round(sample.depth_m, 2),
                        "box_area_fraction": round(
                            ((right - left) * (bottom - top)) / max(rgb.width * rgb.height, 1),
                            5,
                        ),
                        "tree_mask_fraction": round(tree_fraction, 3),
                        "bottom_label": bottom_label,
                        "label_fractions": fractions,
                    }
                )
        print(
            f"audited {min(start + len(batch_ids), len(image_ids))}/{len(image_ids)} images",
            flush=True,
        )
    tree_fractions = [_f(record["tree_mask_fraction"]) for record in records]
    bottom_counts: dict[str, int] = {}
    for record in records:
        label = str(record["bottom_label"])
        bottom_counts[label] = bottom_counts.get(label, 0) + 1
    payload: dict[str, object] = {
        "schema_version": "fresh-urban-forest.street-tree-mask-audit.v1",
        "phase": "P69",
        "requested_samples": args.per_stratum * 4,
        "sample_count": len(records),
        "stratum_targets": stratum_counts,
        "stratum_actual": {
            name: sum(1 for record in records if record["stratum"] == name)
            for name in stratum_counts
        },
        "tree_mask_fraction": {
            "min": round(min(tree_fractions), 3) if tree_fractions else None,
            "median": round(statistics.median(tree_fractions), 3) if tree_fractions else None,
            "p25": round(float(np.quantile(tree_fractions, 0.25)), 3) if tree_fractions else None,
            "p75": round(float(np.quantile(tree_fractions, 0.75)), 3) if tree_fractions else None,
            "max": round(max(tree_fractions), 3) if tree_fractions else None,
            "below_0_25": sum(value < 0.25 for value in tree_fractions),
            "below_0_50": sum(value < 0.50 for value in tree_fractions),
        },
        "bottom_centre_label_counts": dict(
            sorted(bottom_counts.items(), key=lambda item: -item[1])
        ),
        "samples": records,
        "contact_sheets": _contact_sheets(samples, args.images_dir, args.sheets_dir),
        "note": (
            "Descriptive audit of the existing semantic model; not a field-validated "
            "precision or recall estimate."
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
    parser.add_argument("--images-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sheets-dir", type=Path, required=True)
    parser.add_argument("--per-stratum", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--device", default="auto")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the mask audit.

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
