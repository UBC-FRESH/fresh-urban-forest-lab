#!/usr/bin/env python3
"""Fuse Vancouver image-CNN probabilities with CHM crown features."""

from __future__ import annotations

import gzip
import json
import math
from pathlib import Path

import numpy as np

from fresh_urban_forest.crown_features import crown_features
from fresh_urban_forest.terrain import project_lonlat, read_raster

ROOT = Path("data/processed/vancouver_2022")
REPORT = Path("data/processed/imagery_classifier/fusion_chm_report.json")


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exponent = math.exp(value)
    return exponent / (1.0 + exponent)


def main() -> int:  # pragma: no cover - operator path
    """Apply the held-out fusion model to Vancouver candidates.

    Returns
    -------
    int
        Process status.
    """
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    fused = report["fused_model"]
    coefficients = np.asarray(fused["coefficients"], dtype=np.float64)
    means = np.asarray(fused["means"], dtype=np.float64)
    scales = np.asarray(fused["scales"], dtype=np.float64)
    intercept = float(fused["intercept"])
    chm = read_raster(ROOT / "chm.tif")
    with gzip.open(ROOT / "off_inventory.geojson.gz", "rt", encoding="utf-8") as handle:
        collection = json.load(handle)
    features = collection["features"]
    high_indices = [
        index
        for index, feature in enumerate(features)
        if float(feature["properties"].get("confidence", 0.0)) >= 0.6
        and feature["properties"].get("imagery_conifer_probability") is not None
    ]
    groups = {"conifer": 0, "deciduous": 0}
    image_groups = {"conifer": 0, "deciduous": 0}
    for index in high_indices:
        properties = features[index]["properties"]
        lon, lat = features[index]["geometry"]["coordinates"]
        x, y = project_lonlat(float(lon), float(lat), "EPSG:3157")
        values = crown_features(chm, x, y).values
        image_probability = float(properties["imagery_conifer_probability"])
        fusion_values = np.asarray([*values, image_probability], dtype=np.float64)
        standardized = (fusion_values - means) / scales
        probability = _sigmoid(float(np.dot(coefficients, standardized) + intercept))
        group = "conifer" if probability >= 0.5 else "deciduous"
        image_group = "conifer" if image_probability >= 0.5 else "deciduous"
        properties["image_group"] = image_group
        properties["image_conifer_probability"] = round(image_probability, 4)
        properties["imagery_group"] = group
        properties["imagery_conifer_probability"] = round(probability, 4)
        properties["fusion_group"] = group
        properties["fusion_conifer_probability"] = round(probability, 4)
        properties["fusion_source"] = "P36 CHM + 2022 image CNN fusion"
        groups[group] += 1
        image_groups[image_group] += 1
    with gzip.open(ROOT / "off_inventory.geojson.gz", "wt", encoding="utf-8") as handle:
        json.dump(collection, handle, separators=(",", ":"))
    summary_path = ROOT / "off_inventory.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["imagery"] = {
        "scored_count": len(high_indices),
        "source": "City of Vancouver Orthophotos 2022",
        "date": "2022",
        "model": "Vancouver 2022 96 px image CNN + independent CHM crown fusion",
        "groups": groups,
        "image_groups": image_groups,
        "known_good_labels": False,
        "caveat": (
            "Candidate scores are screening predictions. The held-out fusion model was "
            "validated on public inventory labels, but off-inventory candidates have no "
            "known-good species-group labels."
        ),
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with gzip.open(ROOT / "off_inventory_3d.json.gz", "rt", encoding="utf-8") as handle:
        compact = json.load(handle)
    high = [features[index]["properties"] for index in high_indices]
    compact["group_code"] = [
        0 if (item.get("imagery_group") or item.get("predicted_group")) == "conifer" else 1
        for item in high[: compact["count"]]
    ]
    compact["fusion_conifer_probability"] = [
        item.get("fusion_conifer_probability") for item in high[: compact["count"]]
    ]
    with gzip.open(ROOT / "off_inventory_3d.json.gz", "wt", encoding="utf-8") as handle:
        json.dump(compact, handle, separators=(",", ":"))
    print("fused", len(high_indices), groups, "image-only", image_groups)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
