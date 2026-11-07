#!/usr/bin/env python3
"""Train a full-resolution Surrey 2025 orthophoto chip classifier."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from fresh_urban_forest.classifier import (
    block_ids,
    brier_score,
    calibration_table,
    classification_metrics,
    holdout_mask,
)
from fresh_urban_forest.fullres_imagery import FullResolutionSource
from fresh_urban_forest.terrain import project_lonlat
from train_imagery_classifier import SmallCNN, _augment

ROOT = Path("data/processed/surrey_2025")
OUT = Path("data/processed/imagery_classifier")
MODEL = OUT / "fullres_surrey_model.pt"
REPORT = OUT / "fullres_surrey_report.json"
CACHE = ROOT / "fullres_surrey_chips.npz"
CHIP = 128


def _read_rows() -> list[dict[str, Any]]:  # pragma: no cover - operator path
    with gzip.open(ROOT / "map_trees.json.gz", "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [item for item in payload.get("features", []) if isinstance(item, dict)]


def _load_dataset(  # pragma: no cover - operator path
    sample_per_class: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if CACHE.is_file() and sample_per_class == 6000:
        payload = np.load(CACHE)
        return payload["images"], payload["labels"], payload["x"], payload["y"]
    rows = _read_rows()
    conifer = [item for item in rows if item.get("properties", {}).get("group") == "conifer"]
    deciduous = [item for item in rows if item.get("properties", {}).get("group") == "deciduous"]
    rng = np.random.default_rng(20261107)
    rng.shuffle(conifer)
    rng.shuffle(deciduous)
    count = min(sample_per_class, len(conifer), len(deciduous))
    selected = conifer[:count] + deciduous[:count]
    labels = np.asarray([1] * count + [0] * count, dtype=np.uint8)
    points = [
        (
            float(item["geometry"]["coordinates"][0]),
            float(item["geometry"]["coordinates"][1]),
        )
        for item in selected
    ]
    xy = np.asarray([project_lonlat(lon, lat, "EPSG:3157") for lon, lat in points])
    source = FullResolutionSource(ROOT / "fullres.vrt", chip_px=CHIP)
    images = np.empty((len(points), CHIP, CHIP, 3), dtype=np.uint8)
    for index, (x, y) in enumerate(xy):
        images[index] = source.chip(float(x), float(y))
        if (index + 1) % 1000 == 0:
            print(f"chips {index + 1}/{len(points)}", flush=True)
    source.close()
    np.savez_compressed(CACHE, images=images, labels=labels, x=xy[:, 0], y=xy[:, 1])
    return images, labels, xy[:, 0], xy[:, 1]


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - operator path
    """Train and evaluate the full-resolution model.

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
    parser.add_argument("--sample-per-class", type=int, default=6000)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args(argv)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available")
    OUT.mkdir(parents=True, exist_ok=True)
    images, labels, x, y = _load_dataset(args.sample_per_class)
    blocks = block_ids(np.asarray(x), np.asarray(y))
    held = holdout_mask(blocks, seed="p37-fullres-2026-11-07")
    train, test = ~held, held
    if len(np.unique(labels[test])) < 2:
        raise RuntimeError("test split lacks one class")
    device = torch.device("cuda")
    model = SmallCNN().to(device)
    counts = np.bincount(labels[train], minlength=2)
    weights = torch.tensor(
        [len(labels[train]) / (2.0 * max(int(count), 1)) for count in counts],
        dtype=torch.float32,
    ).to(device)
    criterion = nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    train_x = torch.from_numpy(images[train].transpose(0, 3, 1, 2).astype(np.float32) / 255.0)
    test_x = torch.from_numpy(images[test].transpose(0, 3, 1, 2).astype(np.float32) / 255.0)
    train_y = torch.from_numpy(labels[train].astype(np.int64))
    test_y = torch.from_numpy(labels[test].astype(np.int64))
    loader = DataLoader(TensorDataset(train_x, train_y), batch_size=args.batch_size, shuffle=True)
    test_loader = DataLoader(TensorDataset(test_x, test_y), batch_size=256)
    best = -1.0
    history: list[dict[str, float]] = []
    for epoch in range(1, args.epochs + 1):
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
        probabilities: list[np.ndarray] = []
        truths: list[np.ndarray] = []
        with torch.no_grad():
            for batch_x, batch_y in test_loader:
                logits = model(batch_x.to(device))
                probabilities.append(torch.softmax(logits, dim=1)[:, 1].cpu().numpy())
                truths.append(batch_y.numpy())
        probability = np.concatenate(probabilities)
        truth = np.concatenate(truths).astype(np.bool_)
        accuracy = float(np.mean((probability >= 0.5) == truth))
        history.append({"epoch": epoch, "loss": running / max(seen, 1), "accuracy": accuracy})
        print(
            f"epoch {epoch}: loss {running / max(seen, 1):.3f} accuracy {accuracy:.4f}",
            flush=True,
        )
        if accuracy > best:
            best = accuracy
            torch.save(model.state_dict(), MODEL)
    model.load_state_dict(torch.load(MODEL, map_location=device, weights_only=True))
    model.eval()
    probabilities = []
    truths = []
    with torch.no_grad():
        for batch_x, batch_y in test_loader:
            logits = model(batch_x.to(device))
            probabilities.append(torch.softmax(logits, dim=1)[:, 1].cpu().numpy())
            truths.append(batch_y.numpy())
    probability = np.concatenate(probabilities)
    truth = np.concatenate(truths).astype(np.bool_)
    metrics = classification_metrics(truth, probability >= 0.5, bootstrap=200)
    metrics["brier_score"] = brier_score(probability, truth)
    metrics["calibration"] = calibration_table(probability, truth)
    report = {
        "schema_version": "fresh-urban-forest.fullres-imagery-classifier.v1",
        "model_family": "small 4-block CNN, 128x128 RGB full-resolution chips",
        "source": "City of Surrey Aerial Photo April 2025, 0.075 m SID",
        "resolution_m": 0.075,
        "chip_px": CHIP,
        "training": {
            "rows": len(labels),
            "train_rows": int(train.sum()),
            "test_rows": int(test.sum()),
            "spatial_block_m": 500,
            "classes": {
                "conifer": int(labels.sum()),
                "deciduous": int((~labels.astype(bool)).sum()),
            },
        },
        "evaluation": metrics,
        "history": history,
        "caveats": [
            "Surrey inventory labels are known-good relative to the inventory, not a field audit.",
            "Imagery is the April 2025 full-resolution SID mosaic.",
            "Coquitlam has no public species inventory.",
            "No stereo interpretation; these are orthorectified images.",
        ],
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("accuracy", metrics["accuracy"], "conifer", metrics["conifer"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
