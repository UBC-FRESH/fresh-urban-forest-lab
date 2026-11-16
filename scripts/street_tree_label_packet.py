"""Build a stratified labeling packet for a future street-tree detector.

This operator script exports crops and a blank label schema only. It does not train a model
and does not modify the canonical layer.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import cast

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.spatial import cKDTree

from street_tree_pilot import _load_inventory


def _f(value: object) -> float:
    """Convert a JSON scalar to float."""
    return float(cast("str | int | float", value))


def _xy(lon: float, lat: float, origin_lon: float, origin_lat: float) -> tuple[float, float]:
    return (
        (lon - origin_lon) * 111_320.0 * math.cos(math.radians(origin_lat)),
        (lat - origin_lat) * 110_540.0,
    )


def _choose(items: list[dict[str, object]], count: int) -> list[dict[str, object]]:
    ordered = sorted(items, key=lambda item: str(item["candidate_id"]))
    if len(ordered) <= count:
        return ordered
    step = len(ordered) / count
    return [ordered[min(len(ordered) - 1, int(index * step))] for index in range(count)]


def run(args: argparse.Namespace) -> dict[str, object]:
    """Build the packet.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed packet arguments.

    Returns
    -------
    dict[str, object]
        Packet summary.
    """
    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))["features"]
    detections = json.loads(args.detections.read_text(encoding="utf-8"))
    by_image: dict[str, list[dict[str, object]]] = {}
    for detection in detections:
        by_image.setdefault(str(detection["image_id"]), []).append(detection)
    inventory = _load_inventory(args.dataset)
    origin_lon, origin_lat = inventory[0][0], inventory[0][1]
    inventory_xy = np.asarray(
        [_xy(lon, lat, origin_lon, origin_lat) for lon, lat, _tree_id in inventory]
    )
    tree = cKDTree(inventory_xy)
    strata: dict[str, list[dict[str, object]]] = {
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
            for detection in by_image.get(str(image_id), []):
                dx, dy = _xy(
                    _f(detection["lon"]),
                    _f(detection["lat"]),
                    lon,
                    lat,
                )
                distance_to_candidate = math.hypot(dx, dy)
                if distance_to_candidate < best_distance:
                    best = detection
                    best_distance = distance_to_candidate
        if best is None:
            continue
        stratum = ("multi" if int(properties["view_count"]) >= 2 else "single") + (
            "_matched" if float(distance) <= 8.0 else "_unmatched"
        )
        strata[stratum].append(
            {
                "candidate_id": str(properties["candidate_id"]),
                "stratum": stratum,
                "view_count": int(properties["view_count"]),
                "score": float(properties["score"]),
                "uncertainty_m": float(properties["positional_uncertainty_m"]),
                "nearest_inventory_m": round(float(distance), 2),
                "image_id": str(best["image_id"]),
                "box": [
                    _f(best["xmin"]),
                    _f(best["ymin"]),
                    _f(best["xmax"]),
                    _f(best["ymax"]),
                ],
            }
        )
    selected: list[dict[str, object]] = []
    for name in strata:
        selected.extend(_choose(strata[name], args.per_stratum))
    packet_dir = args.packet_dir
    crops_dir = packet_dir / "crops"
    sheets_dir = packet_dir / "sheets"
    crops_dir.mkdir(parents=True, exist_ok=True)
    sheets_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, object]] = []
    sheet_rows: dict[str, list[tuple[dict[str, object], Image.Image]]] = {
        name: [] for name in strata
    }
    font = ImageFont.load_default()
    for index, sample in enumerate(selected):
        path = args.images_dir / f"{sample['image_id']}.jpg"
        if not path.is_file():
            continue
        with Image.open(path) as opened:
            image = opened.convert("RGB")
        xmin, ymin, xmax, ymax = (float(value) for value in cast(list[float], sample["box"]))
        pad = max(xmax - xmin, ymax - ymin) * 0.35 + 20
        left = max(0, int(xmin - pad))
        top = max(0, int(ymin - pad))
        right = min(image.width, int(xmax + pad))
        bottom = min(image.height, int(ymax + pad))
        crop = image.crop((left, top, right, bottom)).resize((512, 512))
        draw = ImageDraw.Draw(crop)
        sx = 512 / max(right - left, 1)
        sy = 512 / max(bottom - top, 1)
        draw.rectangle(
            ((xmin - left) * sx, (ymin - top) * sy, (xmax - left) * sx, (ymax - top) * sy),
            outline=(220, 30, 30),
            width=5,
        )
        candidate_id = str(sample["candidate_id"])
        crop_name = f"{index + 1:04d}_{candidate_id.replace(':', '_')}.jpg"
        crop.save(crops_dir / crop_name, quality=90)
        row = {
            **sample,
            "crop": str(crops_dir / crop_name),
            "tree_present": "",
            "trunk_visible": "",
            "box_quality": "",
            "notes": "",
        }
        manifest.append(row)
        if len(sheet_rows[str(sample["stratum"])]) < 100:
            thumb = crop.resize((160, 160))
            sheet_rows[str(sample["stratum"])].append((row, thumb))
    for stratum, items in sheet_rows.items():
        if not items:
            continue
        cols, rows = 10, 10
        sheet = Image.new("RGB", (cols * 160, rows * 186), (247, 245, 239))
        draw = ImageDraw.Draw(sheet)
        for index, (row, thumb) in enumerate(items):
            x = (index % cols) * 160
            y = (index // cols) * 186
            sheet.paste(thumb, (x, y))
            draw.text((x + 2, y + 162), str(row["candidate_id"]), fill=(20, 30, 25), font=font)
        sheet.save(sheets_dir / f"{stratum}.jpg", quality=88)
    manifest_payload = {
        "schema_version": "fresh-urban-forest.street-tree-label-packet.v1",
        "phase": "P73",
        "labels": ["tree_present", "trunk_visible", "box_quality"],
        "samples": manifest,
    }
    args.manifest_out.write_text(
        json.dumps(manifest_payload, indent=2) + "\n",
        encoding="utf-8",
    )
    labels_path = packet_dir / "labels.csv"
    with labels_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "candidate_id",
                "stratum",
                "image_id",
                "tree_present",
                "trunk_visible",
                "box_quality",
                "notes",
            ],
        )
        writer.writeheader()
        for row in manifest:
            writer.writerow({key: row[key] for key in writer.fieldnames})
    summary = {
        "schema_version": "fresh-urban-forest.street-tree-label-packet.v1",
        "phase": "P73",
        "requested_per_stratum": args.per_stratum,
        "sample_count": len(manifest),
        "stratum_counts": {
            name: sum(1 for row in manifest if row["stratum"] == name) for name in strata
        },
        "packet_dir": str(packet_dir),
        "manifest": str(args.manifest_out),
        "labels_csv": str(labels_path),
        "label_schema": {
            "tree_present": "yes / partial / no",
            "trunk_visible": "yes / no",
            "box_quality": "good / loose / bad",
            "notes": "free text",
        },
        "note": "Labels are blank. No model was trained and no canonical data changed.",
    }
    args.out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Parameters
    ----------
    argv : list of str or None
        Arguments. ``None`` uses ``sys.argv``.

    Returns
    -------
    argparse.Namespace
        Parsed packet arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--detections", type=Path, required=True)
    parser.add_argument("--images-dir", type=Path, required=True)
    parser.add_argument("--packet-dir", type=Path, required=True)
    parser.add_argument("--manifest-out", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--per-stratum", type=int, default=100)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the packet builder.

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
