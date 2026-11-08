#!/usr/bin/env python3
"""Evaluate the Vancouver 0.30 m image model on Surrey inventory labels."""

from __future__ import annotations

import gzip
import importlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image

from fresh_urban_forest.classifier import (
    block_ids,
    brier_score,
    calibration_table,
    classification_metrics,
    holdout_mask,
)
from fresh_urban_forest.terrain import project_lonlat
from train_imagery_classifier import SmallCNN

SURREY = Path("data/processed/surrey_2025")
MODEL = Path("data/processed/imagery_classifier/model.pt")
REPORT = Path("data/processed/imagery_classifier/surrey_transfer_report.json")
VRT = SURREY / "fullres.vrt"
CHIP = 96
SOURCE_CHIP = 384
SAMPLE_PER_CLASS = 6000


def _gdal() -> Any:  # noqa: ANN401  # pragma: no cover - optional GDAL binding
    """Import GDAL lazily because CI does not install the optional binding.

    Returns
    -------
    Any
        The imported ``osgeo.gdal`` module.
    """
    return importlib.import_module("osgeo.gdal")


def _read_labels() -> list[dict[str, Any]]:  # pragma: no cover - operator path
    with gzip.open(SURREY / "map_trees.json.gz", "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [item for item in payload.get("features", []) if isinstance(item, dict)]


def _bsq_to_rgb(payload: bytes, size: int) -> np.ndarray:  # pragma: no cover - operator path
    values = np.frombuffer(payload, dtype=np.uint8)
    return np.ascontiguousarray(values.reshape(3, size, size).transpose(1, 2, 0))


def _read_chip(  # pragma: no cover - operator path
    gdal: Any,  # noqa: ANN401  # optional GDAL binding
    dataset: Any,  # noqa: ANN401  # optional GDAL binding
    inverse: tuple[float, ...],
    x: float,
    y: float,
) -> np.ndarray:
    px, py = gdal.ApplyGeoTransform(inverse, x, y)
    left = round(px - SOURCE_CHIP / 2)
    top = round(py - SOURCE_CHIP / 2)
    xoff = max(left, 0)
    yoff = max(top, 0)
    xend = min(left + SOURCE_CHIP, dataset.RasterXSize)
    yend = min(top + SOURCE_CHIP, dataset.RasterYSize)
    canvas = np.zeros((SOURCE_CHIP, SOURCE_CHIP, 3), dtype=np.uint8)
    if xend <= xoff or yend <= yoff:
        return np.asarray(Image.fromarray(canvas).resize((CHIP, CHIP), Image.Resampling.BILINEAR))
    payload = dataset.ReadRaster(
        xoff,
        yoff,
        xend - xoff,
        yend - yoff,
        buf_xsize=CHIP,
        buf_ysize=CHIP,
        band_list=[1, 2, 3],
    )
    # GDAL returns band-sequential bytes for this VRT; resize is done by GDAL here.
    image = np.frombuffer(payload, dtype=np.uint8).reshape(3, CHIP, CHIP).transpose(1, 2, 0)
    return np.asarray(Image.fromarray(image).resize((CHIP, CHIP), Image.Resampling.BILINEAR))


def main() -> int:  # pragma: no cover - operator path
    """Evaluate the Vancouver model on the Surrey inventory holdout.

    Returns
    -------
    int
        Process status.
    """
    rows = _read_labels()
    conifer = [row for row in rows if row.get("properties", {}).get("group") == "conifer"]
    deciduous = [row for row in rows if row.get("properties", {}).get("group") == "deciduous"]
    rng = np.random.default_rng(20261108)
    rng.shuffle(conifer)
    rng.shuffle(deciduous)
    count = min(SAMPLE_PER_CLASS, len(conifer), len(deciduous))
    selected = conifer[:count] + deciduous[:count]
    labels = np.asarray([1] * count + [0] * count, dtype=np.uint8)
    points = [
        (
            float(row["geometry"]["coordinates"][0]),
            float(row["geometry"]["coordinates"][1]),
        )
        for row in selected
    ]
    x = np.asarray([project_lonlat(lon, lat, "EPSG:3157")[0] for lon, lat in points])
    y = np.asarray([project_lonlat(lon, lat, "EPSG:3157")[1] for lon, lat in points])
    gdal = _gdal()
    dataset = gdal.Open(str(VRT))
    if dataset is None:
        raise SystemExit(f"cannot open {VRT}")
    inverse = gdal.InvGeoTransform(dataset.GetGeoTransform())
    images = np.empty((len(points), CHIP, CHIP, 3), dtype=np.uint8)
    for index, (x_value, y_value) in enumerate(zip(x, y, strict=True)):
        images[index] = _read_chip(gdal, dataset, inverse, float(x_value), float(y_value))
        if (index + 1) % 1000 == 0:
            print("chips", index + 1, "/", len(points), flush=True)
    blocks = block_ids(x, y)
    held = holdout_mask(blocks, seed="p45-surrey-image-2026-11-08")
    train, test = ~held, held
    if len(np.unique(labels[test])) < 2:
        raise SystemExit("test split lacks one class")
    device = torch.device("cuda")
    model = SmallCNN().to(device)
    model.load_state_dict(torch.load(MODEL, map_location=device, weights_only=True))
    model.eval()
    probabilities = []
    with torch.no_grad():
        for start in range(0, int(test.sum()), 256):
            batch_index = np.flatnonzero(test)[start : start + 256]
            tensor = torch.from_numpy(
                images[batch_index].transpose(0, 3, 1, 2).astype(np.float32) / 255.0
            ).to(device)
            probabilities.append(torch.softmax(model(tensor), dim=1)[:, 1].cpu().numpy())
    probability = np.concatenate(probabilities)
    truth = labels[test].astype(np.bool_)
    metrics = classification_metrics(truth, probability >= 0.5, bootstrap=200)
    metrics["brier_score"] = brier_score(probability, truth)
    metrics["calibration"] = calibration_table(probability, truth)
    report = {
        "schema_version": "fresh-urban-forest.surrey-image-transfer.v1",
        "model": "Vancouver 2022 96 px image CNN (transfer only)",
        "source": "City of Surrey Aerial Photo April 2025, downsampled to 0.30 m",
        "labels": "Surrey public tree inventory",
        "chip_px": CHIP,
        "source_chip_px": SOURCE_CHIP,
        "sample_per_class": count,
        "training": {
            "rows": len(labels),
            "train_rows": int(train.sum()),
            "test_rows": int(test.sum()),
            "spatial_block_m": 500,
        },
        "evaluation": metrics,
        "caveats": [
            "This evaluates inventory labels, not off-inventory candidates.",
            "The model was trained on Vancouver 2022 imagery and is transferred "
            "without Surrey fine-tuning.",
            "No field validation.",
        ],
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"accuracy": metrics["accuracy"], "conifer": metrics["conifer"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
