#!/usr/bin/env python3
"""Score and preflight a Surrey 0.30 m candidate audit sample."""

from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image

from fresh_urban_forest.terrain import project_lonlat
from train_imagery_classifier import SmallCNN

ROOT = Path("data/processed/surrey_2025")
OUT = ROOT / "p47_audit"
MODEL = Path("data/processed/imagery_classifier/surrey03_model.pt")
SIZE = 384
SAMPLE_PER_BIN = 20


def main() -> int:  # pragma: no cover - operator path
    """Build the preflighted audit key.

    Returns
    -------
    int
        Process status.
    """
    from fresh_urban_forest.fullres_imagery import FullResolutionSource

    OUT.mkdir(parents=True, exist_ok=True)
    with gzip.open(ROOT / "off_inventory.geojson.gz", "rt", encoding="utf-8") as handle:
        collection = json.load(handle)
    features = collection["features"]
    high = [
        (index, feature)
        for index, feature in enumerate(features)
        if float(feature["properties"]["confidence"]) >= 0.6
    ]
    rng = np.random.default_rng(20261108)
    buckets: list[list[tuple[int, dict[str, Any]]]] = []
    for low in np.linspace(0.0, 1.0, 11)[:-1]:
        high_bound = low + 0.1
        bucket = [
            (index, feature)
            for index, feature in high
            if low
            <= float(feature["properties"].get("image_conifer_probability", 0.0))
            < high_bound
        ]
        rng.shuffle(bucket)
        buckets.append(bucket)
    source = FullResolutionSource(ROOT / "fullres.vrt", chip_px=SIZE)
    device = torch.device("cuda")
    model = SmallCNN().to(device)
    model.load_state_dict(torch.load(MODEL, map_location=device, weights_only=True))
    model.eval()
    accepted: list[dict[str, Any]] = []
    rejected = 0
    for bucket in buckets:
        taken = 0
        for index, feature in bucket:
            if taken >= SAMPLE_PER_BIN:
                break
            lon, lat = feature["geometry"]["coordinates"]
            x, y = project_lonlat(float(lon), float(lat), "EPSG:3157")
            wide = source.chip(float(x), float(y), size=SIZE)
            mean = float(np.mean(wide))
            std = float(np.std(wide))
            maximum = int(np.max(wide))
            if mean < 5.0 or std < 5.0 or maximum < 30:
                rejected += 1
                continue
            chip = np.asarray(Image.fromarray(wide).resize((96, 96), Image.Resampling.BILINEAR))
            tensor = torch.from_numpy(chip.transpose(2, 0, 1).astype(np.float32)[None] / 255.0).to(
                device
            )
            with torch.no_grad():
                probability = float(torch.softmax(model(tensor), dim=1)[0, 1].item())
            accepted.append(
                {
                    "candidate_index": index,
                    "candidate_id": feature["properties"]["candidate_id"],
                    "p_fullres": (
                        f"{float(feature['properties'].get('image_conifer_probability', 0.0)):.6f}"
                    ),
                    "p_030": f"{probability:.6f}",
                    "page": len(accepted) // 20 + 1,
                    "mean": f"{mean:.2f}",
                    "std": f"{std:.2f}",
                    "max": str(maximum),
                }
            )
            taken += 1
        print("bin accepted", len(accepted), "rejected", rejected, flush=True)
    source.close()
    with (OUT / "audit_key.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "candidate_index",
                "candidate_id",
                "p_fullres",
                "p_030",
                "page",
                "mean",
                "std",
                "max",
            ],
        )
        writer.writeheader()
        writer.writerows(accepted)
    (OUT / "preflight.json").write_text(
        json.dumps(
            {
                "sampled": len(high),
                "accepted": len(accepted),
                "rejected": rejected,
                "minimum_mean": min(float(row["mean"]) for row in accepted),
                "minimum_std": min(float(row["std"]) for row in accepted),
                "minimum_max": min(int(row["max"]) for row in accepted),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("accepted", len(accepted), "rejected", rejected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
