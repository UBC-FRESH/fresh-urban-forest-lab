#!/usr/bin/env python3
"""Score Surrey or Coquitlam candidates with the full-resolution image model."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np
import torch

from fresh_urban_forest.fullres_imagery import FullResolutionSource
from fresh_urban_forest.terrain import project_lonlat
from train_imagery_classifier import SmallCNN

CITIES = {
    "surrey_2025": {
        "label": "Surrey",
        "source": "City of Surrey Aerial Photo April 2025, 0.075 m SID",
        "date": "2025",
    },
    "coquitlam_2025": {
        "label": "Coquitlam",
        "source": "City of Coquitlam Orthophoto 2025, 0.075 m SID",
        "date": "2025",
    },
}
MODEL = Path("data/processed/imagery_classifier/fullres_surrey_model.pt")
CHIP = 128
BATCH = 1024


def _write_city(city: str) -> None:  # pragma: no cover - operator path
    root = Path("data/processed") / city
    meta = CITIES[city]
    with gzip.open(root / "off_inventory.geojson.gz", "rt", encoding="utf-8") as handle:
        collection = json.load(handle)
    features = collection["features"]
    indices = [
        index
        for index, feature in enumerate(features)
        if float(feature["properties"]["confidence"]) >= 0.6
    ]
    print(city, "high-confidence candidates", len(indices), flush=True)
    xy = np.asarray(
        [
            project_lonlat(
                float(features[index]["geometry"]["coordinates"][0]),
                float(features[index]["geometry"]["coordinates"][1]),
                "EPSG:3157",
            )
            for index in indices
        ],
        dtype=np.float64,
    )
    source = FullResolutionSource(root / "fullres.vrt", chip_px=CHIP)
    device = torch.device("cuda")
    model = SmallCNN().to(device)
    model.load_state_dict(torch.load(MODEL, map_location=device, weights_only=True))
    model.eval()
    probabilities = np.empty(len(indices), dtype=np.float64)
    with torch.no_grad():
        for start in range(0, len(indices), BATCH):
            stop = min(start + BATCH, len(indices))
            batch = np.empty((stop - start, CHIP, CHIP, 3), dtype=np.uint8)
            for offset, (x, y) in enumerate(xy[start:stop]):
                batch[offset] = source.chip(float(x), float(y))
            tensor = torch.from_numpy(batch.transpose(0, 3, 1, 2).astype(np.float32) / 255.0).to(
                device
            )
            values = torch.softmax(model(tensor), dim=1)[:, 1].cpu().numpy()
            probabilities[start:stop] = values
            if (start + BATCH) % (BATCH * 10) == 0 or stop == len(indices):
                print("scored", stop, "/", len(indices), flush=True)
    source.close()
    counts = {"conifer": 0, "deciduous": 0}
    for index, probability in zip(indices, probabilities, strict=True):
        properties = features[index]["properties"]
        group = "conifer" if probability >= 0.5 else "deciduous"
        properties.update(
            {
                "image_group": group,
                "image_conifer_probability": round(float(probability), 4),
                "imagery_group": group,
                "imagery_conifer_probability": round(float(probability), 4),
                "imagery_source": meta["source"],
                "imagery_date": meta["date"],
                "imagery_resolution_m": 0.075,
                "imagery_model": "P37 full-resolution Surrey 2025 CNN",
            }
        )
        for key in ("fusion_group", "fusion_conifer_probability", "fusion_source"):
            properties.pop(key, None)
        counts[group] += 1
    with gzip.open(root / "off_inventory.geojson.gz", "wt", encoding="utf-8") as handle:
        json.dump(collection, handle, separators=(",", ":"))
    summary_path = root / "off_inventory.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    caveat = (
        "Candidate scores are screening predictions. Surrey public-tree labels are "
        "known-good relative to the inventory, but off-inventory candidates have no "
        "known-good species-group labels."
        if city == "surrey_2025"
        else (
            "Candidate scores are screening predictions. Coquitlam has no public species "
            "inventory, so this is not a known-good species test."
        )
    )
    summary["imagery"] = {
        "scored_count": len(probabilities),
        "source": meta["source"],
        "date": meta["date"],
        "resolution_m": 0.075,
        "model": "P37 full-resolution Surrey 2025 CNN",
        "groups": counts,
        "known_good_labels": False,
        "caveat": caveat,
    }
    if city == "surrey_2025":
        report_path = Path("data/processed/imagery_classifier/fullres_surrey_report.json")
        if report_path.is_file():
            summary["imagery"]["validation"] = json.loads(report_path.read_text(encoding="utf-8"))[
                "evaluation"
            ]
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with gzip.open(root / "off_inventory_3d.json.gz", "rt", encoding="utf-8") as handle:
        compact = json.load(handle)
    high = [features[index]["properties"] for index in indices]
    compact["group_code"] = [
        0 if item["imagery_group"] == "conifer" else 1 for item in high[: compact["count"]]
    ]
    compact["imagery_conifer_probability"] = [
        item["imagery_conifer_probability"] for item in high[: compact["count"]]
    ]
    compact.pop("fusion_conifer_probability", None)
    with gzip.open(root / "off_inventory_3d.json.gz", "wt", encoding="utf-8") as handle:
        json.dump(compact, handle, separators=(",", ":"))
    print(city, "scored", len(probabilities), counts, flush=True)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - operator path
    """Score one or both cities.

    Parameters
    ----------
    argv : list of str or None
        Command-line arguments.

    Returns
    -------
    int
        Process status.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", choices=[*CITIES, "both"], default="both")
    args = parser.parse_args(argv)
    cities = list(CITIES) if args.city == "both" else [args.city]
    for city in cities:
        _write_city(city)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
