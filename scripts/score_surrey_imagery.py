#!/usr/bin/env python3
"""Score Surrey off-inventory candidates with the P36 image and fusion models."""

from __future__ import annotations

import gzip
import io
import json
import math
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import torch
from PIL import Image

from fresh_urban_forest.crown_features import crown_features
from fresh_urban_forest.terrain import project_lonlat, read_raster
from train_imagery_classifier import SmallCNN

ROOT = Path("data/processed/surrey_2025")
CACHE = Path("data/raw/imagery_cache/surrey_2025")
CACHE.mkdir(parents=True, exist_ok=True)
MODEL = Path("data/processed/imagery_classifier/model.pt")
FUSION = Path("data/processed/imagery_classifier/fusion_chm_report.json")
SERVICE = "https://gisservices.surrey.ca/arcgis/rest/services/AerialImages/MapServer/export"
SIZE = 96
CHUNK_M = 1200
STRIDE_M = 1000
IMAGE_PX = 4096


def _export(
    left: float, bottom: float, right: float, top: float
) -> Image.Image:  # pragma: no cover
    """Export one 2025 orthophoto chunk."""
    key = f"{left:.0f}_{bottom:.0f}_{right:.0f}_{top:.0f}"
    path = CACHE / f"{key}.jpg"
    if path.is_file() and path.stat().st_size:
        return Image.open(path).convert("RGB")
    params = {
        "bbox": f"{left},{bottom},{right},{top}",
        "bboxSR": "3157",
        "imageSR": "3157",
        "size": f"{IMAGE_PX},{IMAGE_PX}",
        "format": "jpg",
        "f": "image",
        "layers": "show:0",
    }
    request = Request(
        f"{SERVICE}?{urlencode(params)}",
        headers={"User-Agent": "FRESH-Urban-Forest-Lab/0.3 imagery score"},
    )
    with urlopen(request, timeout=180) as response:
        payload = response.read()
    path.write_bytes(payload)
    return Image.open(io.BytesIO(payload)).convert("RGB")


def _chunk_key(x: float, y: float, bounds: tuple[float, float, float, float]) -> tuple[int, int]:
    left, _bottom, _right, top = bounds
    return (
        math.floor((x - left - 100.0) / STRIDE_M),
        math.floor((top - y - 100.0) / STRIDE_M),
    )


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exponent = math.exp(value)
    return exponent / (1.0 + exponent)


def main() -> int:  # pragma: no cover - operator path
    """Run Surrey candidate image and fusion scoring.

    Returns
    -------
    int
        Process status.
    """
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    bounds = (
        float(manifest["bounds"][0]),
        float(manifest["bounds"][1]),
        float(manifest["bounds"][2]),
        float(manifest["bounds"][3]),
    )
    left, _bottom, _right, top = bounds
    with gzip.open(ROOT / "off_inventory.geojson.gz", "rt", encoding="utf-8") as handle:
        collection = json.load(handle)
    features = collection["features"]
    scored = [
        index
        for index, feature in enumerate(features)
        if float(feature["properties"]["confidence"]) >= 0.6
    ]
    print("high-confidence candidates", len(scored), flush=True)
    chunks: dict[tuple[int, int], list[int]] = {}
    for index in scored:
        lon, lat = features[index]["geometry"]["coordinates"]
        x, y = project_lonlat(float(lon), float(lat), "EPSG:3157")
        chunks.setdefault(_chunk_key(x, y, bounds), []).append(index)
    device = torch.device("cuda")
    model = SmallCNN().to(device)
    model.load_state_dict(torch.load(MODEL, map_location=device, weights_only=True))
    model.eval()
    probabilities: dict[int, float] = {}
    for number, (key, indices) in enumerate(sorted(chunks.items()), start=1):
        col, row = key
        chunk_left = left + col * STRIDE_M
        chunk_top = top - row * STRIDE_M
        chunk_right = chunk_left + CHUNK_M
        chunk_bottom = chunk_top - CHUNK_M
        try:
            image = _export(chunk_left, chunk_bottom, chunk_right, chunk_top)
        except Exception as error:  # pragma: no cover - network path
            print("chunk failed", key, error, flush=True)
            continue
        chips = []
        valid_indices = []
        scale = IMAGE_PX / CHUNK_M
        for index in indices:
            lon, lat = features[index]["geometry"]["coordinates"]
            x, y = project_lonlat(float(lon), float(lat), "EPSG:3157")
            px = (x - chunk_left) * scale
            py = (chunk_top - y) * scale
            if (
                px < SIZE / 2
                or py < SIZE / 2
                or px >= IMAGE_PX - SIZE / 2
                or py >= IMAGE_PX - SIZE / 2
            ):
                continue
            box = (
                round(px - SIZE / 2),
                round(py - SIZE / 2),
                round(px + SIZE / 2),
                round(py + SIZE / 2),
            )
            chips.append(np.asarray(image.crop(box), dtype=np.uint8))
            valid_indices.append(index)
        if not chips:
            continue
        tensor = torch.from_numpy(
            np.stack(chips, axis=0).transpose(0, 3, 1, 2).astype(np.float32) / 255.0
        )
        with torch.no_grad():
            values = torch.softmax(model(tensor.to(device)), dim=1)[:, 1].cpu().numpy()
        for index, value in zip(valid_indices, values, strict=True):
            probabilities[int(index)] = float(value)
        if number % 25 == 0:
            print(f"chunk {number}/{len(chunks)}: {len(probabilities)} scored", flush=True)

    report = json.loads(FUSION.read_text(encoding="utf-8"))
    fused = report["fused_model"]
    coefficients = np.asarray(fused["coefficients"], dtype=np.float64)
    means = np.asarray(fused["means"], dtype=np.float64)
    scales = np.asarray(fused["scales"], dtype=np.float64)
    intercept = float(fused["intercept"])
    chm = read_raster(ROOT / "_chm.tif")
    counts = {"conifer": 0, "deciduous": 0}
    image_counts = {"conifer": 0, "deciduous": 0}
    for index, probability in probabilities.items():
        properties = features[index]["properties"]
        lon, lat = features[index]["geometry"]["coordinates"]
        x, y = project_lonlat(float(lon), float(lat), "EPSG:3157")
        chm_values = np.asarray(crown_features(chm, x, y).values, dtype=np.float64)
        fusion_values = np.asarray([*chm_values, probability], dtype=np.float64)
        standardized = (fusion_values - means) / scales
        fused_probability = _sigmoid(float(np.dot(coefficients, standardized) + intercept))
        group = "conifer" if fused_probability >= 0.5 else "deciduous"
        image_group = "conifer" if probability >= 0.5 else "deciduous"
        properties.update(
            {
                "image_group": image_group,
                "image_conifer_probability": round(probability, 4),
                "imagery_group": group,
                "imagery_conifer_probability": round(fused_probability, 4),
                "fusion_group": group,
                "fusion_conifer_probability": round(fused_probability, 4),
                "imagery_source": "City of Surrey Aerial Photo April 2025",
                "imagery_date": "2025",
                "fusion_source": "P36 CHM + image CNN fusion",
            }
        )
        counts[group] += 1
        image_counts[image_group] += 1
    with gzip.open(ROOT / "off_inventory.geojson.gz", "wt", encoding="utf-8") as handle:
        json.dump(collection, handle, separators=(",", ":"))
    summary_path = ROOT / "off_inventory.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["imagery"] = {
        "scored_count": len(probabilities),
        "source": "City of Surrey Aerial Photo April 2025",
        "date": "2025",
        "model": "Vancouver 2022 image CNN + CHM fusion",
        "groups": counts,
        "image_groups": image_counts,
        "known_good_labels": False,
        "caveat": (
            "Candidate scores are screening predictions. Surrey public-tree labels are "
            "known-good relative to the inventory, but off-inventory candidates have no "
            "known-good species-group labels."
        ),
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with gzip.open(ROOT / "off_inventory_3d.json.gz", "rt", encoding="utf-8") as handle:
        compact = json.load(handle)
    high = [features[index]["properties"] for index in scored]
    compact["group_code"] = [
        0 if (item.get("imagery_group") or item.get("predicted_group")) == "conifer" else 1
        for item in high[: compact["count"]]
    ]
    compact["fusion_conifer_probability"] = [
        item.get("fusion_conifer_probability") for item in high[: compact["count"]]
    ]
    with gzip.open(ROOT / "off_inventory_3d.json.gz", "wt", encoding="utf-8") as handle:
        json.dump(compact, handle, separators=(",", ":"))
    print("scored", len(probabilities), "fused", counts, "image", image_counts, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
