#!/usr/bin/env python3
"""Train and evaluate a Surrey-specific 0.30 m image model."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from evaluate_surrey_image_transfer import CHIP, SOURCE_CHIP, _gdal, _read_chip
from fresh_urban_forest.classifier import (
    block_ids,
    brier_score,
    calibration_table,
    classification_metrics,
    holdout_mask,
)
from fresh_urban_forest.terrain import project_lonlat
from train_imagery_classifier import SmallCNN, _augment

SURREY = Path("data/processed/surrey_2025")
BASE_MODEL = Path("data/processed/imagery_classifier/model.pt")
MODEL = Path("data/processed/imagery_classifier/surrey03_model.pt")
REPORT = Path("data/processed/imagery_classifier/surrey03_report.json")
CACHE = Path("data/processed/imagery_classifier/surrey03_chips.npz")
SAMPLE_PER_CLASS = 6000


def _load() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:  # pragma: no cover
    if CACHE.is_file():
        payload = np.load(CACHE)
        return payload["images"], payload["labels"], payload["x"], payload["y"]
    with gzip.open(SURREY / "map_trees.json.gz", "rt", encoding="utf-8") as handle:
        rows = json.load(handle)["features"]
    conifer = [row for row in rows if row.get("properties", {}).get("group") == "conifer"]
    deciduous = [row for row in rows if row.get("properties", {}).get("group") == "deciduous"]
    rng = np.random.default_rng(20261108)
    rng.shuffle(conifer)
    rng.shuffle(deciduous)
    count = min(SAMPLE_PER_CLASS, len(conifer), len(deciduous))
    selected = conifer[:count] + deciduous[:count]
    labels = np.asarray([1] * count + [0] * count, dtype=np.uint8)
    points = [
        (float(row["geometry"]["coordinates"][0]), float(row["geometry"]["coordinates"][1]))
        for row in selected
    ]
    x = np.asarray([project_lonlat(lon, lat, "EPSG:3157")[0] for lon, lat in points])
    y = np.asarray([project_lonlat(lon, lat, "EPSG:3157")[1] for lon, lat in points])
    gdal = _gdal()
    dataset = gdal.Open(str(SURREY / "fullres.vrt"))
    if dataset is None:
        raise SystemExit("cannot open Surrey full-resolution VRT")
    inverse = gdal.InvGeoTransform(dataset.GetGeoTransform())
    images = np.empty((len(points), CHIP, CHIP, 3), dtype=np.uint8)
    for index, (x_value, y_value) in enumerate(zip(x, y, strict=True)):
        images[index] = _read_chip(gdal, dataset, inverse, float(x_value), float(y_value))
        if (index + 1) % 1000 == 0:
            print("chips", index + 1, "/", len(points), flush=True)
    np.savez_compressed(CACHE, images=images, labels=labels, x=x, y=y)
    return images, labels, x, y


def main() -> int:  # pragma: no cover - operator path
    """Train and evaluate the Surrey 0.30 m model.

    Returns
    -------
    int
        Process status.
    """
    if not torch.cuda.is_available():
        raise SystemExit("CUDA is not available")
    images, labels, x, y = _load()
    held = holdout_mask(block_ids(x, y), seed="p45-surrey-image-2026-11-08")
    train, test = ~held, held
    device = torch.device("cuda")
    model = SmallCNN().to(device)
    model.load_state_dict(torch.load(BASE_MODEL, map_location=device, weights_only=True))
    counts = np.bincount(labels[train], minlength=2)
    weights = torch.tensor(
        [len(labels[train]) / (2.0 * max(int(count), 1)) for count in counts],
        dtype=torch.float32,
    ).to(device)
    criterion = nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    train_x = torch.from_numpy(images[train].transpose(0, 3, 1, 2).astype(np.float32) / 255.0)
    test_x = torch.from_numpy(images[test].transpose(0, 3, 1, 2).astype(np.float32) / 255.0)
    train_y = torch.from_numpy(labels[train].astype(np.int64))
    test_y = torch.from_numpy(labels[test].astype(np.int64))
    loader = DataLoader(TensorDataset(train_x, train_y), batch_size=64, shuffle=True)
    test_loader = DataLoader(TensorDataset(test_x, test_y), batch_size=256)
    best = -1.0
    history = []
    for epoch in range(1, 11):
        model.train()
        running = 0.0
        seen = 0
        for batch_x, batch_y in loader:
            batch_x = _augment(batch_x).to(device)
            batch_y = batch_y.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(batch_x), batch_y)
            loss.backward()
            optimizer.step()
            running += float(loss.item()) * batch_x.shape[0]
            seen += batch_x.shape[0]
        model.eval()
        values = []
        truths = []
        with torch.no_grad():
            for batch_x, batch_y in test_loader:
                values.append(torch.softmax(model(batch_x.to(device)), dim=1)[:, 1].cpu().numpy())
                truths.append(batch_y.numpy())
        probability = np.concatenate(values)
        truth = np.concatenate(truths).astype(np.bool_)
        accuracy = float(np.mean((probability >= 0.5) == truth))
        history.append({"epoch": epoch, "loss": running / max(seen, 1), "accuracy": accuracy})
        print(f"epoch {epoch}: accuracy {accuracy:.4f}", flush=True)
        if accuracy > best:
            best = accuracy
            torch.save(model.state_dict(), MODEL)
    model.load_state_dict(torch.load(MODEL, map_location=device, weights_only=True))
    model.eval()
    values = []
    truths = []
    with torch.no_grad():
        for batch_x, batch_y in test_loader:
            values.append(torch.softmax(model(batch_x.to(device)), dim=1)[:, 1].cpu().numpy())
            truths.append(batch_y.numpy())
    probability = np.concatenate(values)
    truth = np.concatenate(truths).astype(np.bool_)
    metrics = classification_metrics(truth, probability >= 0.5, bootstrap=200)
    metrics["brier_score"] = brier_score(probability, truth)
    metrics["calibration"] = calibration_table(probability, truth)
    report = {
        "schema_version": "fresh-urban-forest.surrey-03-image.v1",
        "model": "Vancouver P36 CNN fine-tuned on Surrey 2025 0.30 m chips",
        "source": "City of Surrey Aerial Photo April 2025, 0.30 m evaluation footprint",
        "labels": "Surrey public tree inventory",
        "chip_px": CHIP,
        "source_chip_px": SOURCE_CHIP,
        "sample_per_class": SAMPLE_PER_CLASS,
        "training": {
            "rows": len(labels),
            "train_rows": int(train.sum()),
            "test_rows": int(test.sum()),
            "spatial_block_m": 500,
        },
        "evaluation": metrics,
        "history": history,
        "caveats": [
            "Inventory labels, not off-inventory candidates.",
            "Do not promote candidate scores from this inventory-only evaluation.",
            "No field validation.",
        ],
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"accuracy": metrics["accuracy"], "conifer": metrics["conifer"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
