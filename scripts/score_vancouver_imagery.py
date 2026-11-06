#!/usr/bin/env python3
"""Score Vancouver off-inventory candidates with the cached 2022 image CNN."""

from __future__ import annotations

import gzip
import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import torch

from fresh_urban_forest.imagery import TileSource, vancouver_2022_source
from train_imagery_classifier import SmallCNN

ROOT = Path("data/processed/vancouver_2022")
CACHE = Path("data/raw/imagery_cache/vancouver_2022")
MODEL = Path("data/processed/imagery_classifier/model.pt")
SIZE = 96
BATCH = 256


def _prefetch(  # pragma: no cover - operator path
    source: TileSource,
    points: list[tuple[float, float]],
) -> None:
    """Prefetch tiles for all candidate chips."""
    coords: set[tuple[int, int]] = set()
    for lon, lat in points:
        gx, gy = source.global_pixel(lon, lat)
        left, top = gx - SIZE / 2.0, gy - SIZE / 2.0
        tx0, ty0 = math.floor(left / 256.0), math.floor(top / 256.0)
        tx1, ty1 = math.floor((left + SIZE - 1) / 256.0), math.floor((top + SIZE - 1) / 256.0)
        for tx in range(tx0, tx1 + 1):
            for ty in range(ty0, ty1 + 1):
                coords.add((tx, ty))
    print("prefetching", len(coords), "tiles", flush=True)
    with ThreadPoolExecutor(max_workers=32) as executor:
        futures = {executor.submit(source.tile, tx, ty): (tx, ty) for tx, ty in coords}
        for count, future in enumerate(as_completed(futures), start=1):
            try:
                future.result()
            except Exception as error:  # pragma: no cover - network path
                print("tile failed", futures[future], error, flush=True)
            if count % 1000 == 0:
                print("tiles", count, "/", len(coords), flush=True)


def main() -> int:  # pragma: no cover - operator path
    """Run Vancouver candidate image scoring.

    Returns
    -------
    int
        Process status.
    """
    with gzip.open(ROOT / "off_inventory.geojson.gz", "rt", encoding="utf-8") as handle:
        collection = json.load(handle)
    features = collection["features"]
    indices = [
        index
        for index, feature in enumerate(features)
        if float(feature["properties"]["confidence"]) >= 0.6
    ]
    print("high-confidence candidates", len(indices), flush=True)
    points = [
        (
            float(features[index]["geometry"]["coordinates"][0]),
            float(features[index]["geometry"]["coordinates"][1]),
        )
        for index in indices
    ]
    source = vancouver_2022_source(CACHE)
    _prefetch(source, points)
    device = torch.device("cuda")
    model = SmallCNN().to(device)
    model.load_state_dict(torch.load(MODEL, map_location=device, weights_only=True))
    model.eval()
    probabilities: dict[int, float] = {}
    for start in range(0, len(points), BATCH):
        chunk = points[start : start + BATCH]
        chips = np.stack([source.chip(lon, lat, size=SIZE) for lon, lat in chunk], axis=0)
        tensor = torch.from_numpy(chips.transpose(0, 3, 1, 2).astype(np.float32) / 255.0)
        with torch.no_grad():
            logits = model(tensor.to(device))
            values = torch.softmax(logits, dim=1)[:, 1].cpu().numpy()
        for index, value in zip(indices[start : start + BATCH], values, strict=True):
            probabilities[int(index)] = float(value)
        if (start // BATCH) % 100 == 0:
            print("scored", min(start + BATCH, len(points)), "/", len(points), flush=True)
    for index, probability in probabilities.items():
        properties = features[index]["properties"]
        properties["imagery_group"] = "conifer" if probability >= 0.5 else "deciduous"
        properties["imagery_conifer_probability"] = round(probability, 4)
        properties["imagery_source"] = "City of Vancouver Orthophotos 2022"
        properties["imagery_date"] = "2022"
    with gzip.open(ROOT / "off_inventory.geojson.gz", "wt", encoding="utf-8") as handle:
        json.dump(collection, handle, separators=(",", ":"))
    groups = {"conifer": 0, "deciduous": 0}
    for probability in probabilities.values():
        groups["conifer" if probability >= 0.5 else "deciduous"] += 1
    summary_path = ROOT / "off_inventory.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["imagery"] = {
        "scored_count": len(probabilities),
        "source": "City of Vancouver Orthophotos 2022",
        "date": "2022",
        "model": "Vancouver 2022 96 px image CNN + CHM fusion",
        "groups": groups,
        "known_good_labels": False,
        "caveat": (
            "Candidate scores are screening predictions. Training labels come from the "
            "Vancouver inventory, but off-inventory candidates have no known-good labels."
        ),
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with gzip.open(ROOT / "off_inventory_3d.json.gz", "rt", encoding="utf-8") as handle:
        compact = json.load(handle)
    high = [features[index]["properties"] for index in indices]
    compact["group_code"] = [
        0 if (item.get("imagery_group") or item.get("predicted_group")) == "conifer" else 1
        for item in high[: compact["count"]]
    ]
    with gzip.open(ROOT / "off_inventory_3d.json.gz", "wt", encoding="utf-8") as handle:
        json.dump(compact, handle, separators=(",", ":"))
    print("scored", len(probabilities), groups, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
