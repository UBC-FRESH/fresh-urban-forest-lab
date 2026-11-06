#!/usr/bin/env python3
"""Score Burnaby off-inventory candidates with the Vancouver image CNN."""

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

from fresh_urban_forest.terrain import project_lonlat
from train_imagery_classifier import SmallCNN, _augment  # noqa: F401

ROOT = Path("data/processed/burnaby_2022")
CACHE = Path("data/raw/imagery_cache/burnaby_2025")
CACHE.mkdir(parents=True, exist_ok=True)
MODEL = Path("data/processed/imagery_classifier/model.pt")
SERVICE = "https://gis.burnaby.ca/arcgis/rest/services/Basemaps/Burnaby_Ortho_2025/MapServer/export"
SIZE = 96
CHUNK_M = 1200
STRIDE_M = 1000
IMAGE_PX = 4096


def _export(  # pragma: no cover - operator path
    left: float,
    bottom: float,
    right: float,
    top: float,
) -> Image.Image:
    """Export one orthophoto chunk."""
    key = f"{left:.0f}_{bottom:.0f}_{right:.0f}_{top:.0f}"
    path = CACHE / f"{key}.jpg"
    if path.is_file():
        return Image.open(path).convert("RGB")
    params = {
        "bbox": f"{left},{bottom},{right},{top}",
        "bboxSR": "3157",
        "imageSR": "3157",
        "size": f"{IMAGE_PX},{IMAGE_PX}",
        "format": "jpg",
        "f": "image",
    }
    request = Request(
        f"{SERVICE}?{urlencode(params)}",
        headers={"User-Agent": "FRESH-Urban-Forest-Lab/0.3 imagery score"},
    )
    with urlopen(request, timeout=120) as response:
        payload = response.read()
    path.write_bytes(payload)
    return Image.open(io.BytesIO(payload)).convert("RGB")


def _chunk_key(  # pragma: no cover - operator path
    x: float,
    y: float,
    bounds: tuple[float, float, float, float],
) -> tuple[int, int]:
    """Return a chunk key that leaves a margin around each point."""
    left, _bottom, _right, top = bounds
    col = math.floor((x - left - 100.0) / STRIDE_M)
    row = math.floor((top - y - 100.0) / STRIDE_M)
    return int(col), int(row)


def main() -> int:  # pragma: no cover - operator path
    """Run the Burnaby image scoring pass.

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
    left, _bottom, _right, top = bounds
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
            logits = model(tensor.to(device))
            values = torch.softmax(logits, dim=1)[:, 1].cpu().numpy()
        for index, value in zip(valid_indices, values, strict=True):
            probabilities[int(index)] = float(value)
        print(f"chunk {number}/{len(chunks)}: {len(chips)} scored", flush=True)
    for index, probability in probabilities.items():
        properties = features[index]["properties"]
        properties["imagery_group"] = "conifer" if probability >= 0.5 else "deciduous"
        properties["imagery_conifer_probability"] = round(probability, 4)
        properties["imagery_source"] = "City of Burnaby Orthophoto 2025"
        properties["imagery_date"] = "2025"
    with gzip.open(ROOT / "off_inventory.geojson.gz", "wt", encoding="utf-8") as handle:
        json.dump(collection, handle, separators=(",", ":"))
    summary_path = ROOT / "off_inventory.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    counts = {"conifer": 0, "deciduous": 0}
    for probability in probabilities.values():
        counts["conifer" if probability >= 0.5 else "deciduous"] += 1
    summary["imagery"] = {
        "scored_count": len(probabilities),
        "source": "City of Burnaby Orthophoto 2025",
        "date": "2025",
        "model": "Vancouver 2022 96 px image CNN",
        "groups": counts,
        "known_good_labels": False,
        "caveat": (
            "Image scores are screening predictions; Burnaby has no public species inventory."
        ),
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("scored", len(probabilities), counts, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
