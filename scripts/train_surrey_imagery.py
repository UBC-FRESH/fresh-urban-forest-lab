#!/usr/bin/env python3
"""Fine-tune the image CNN on Surrey 2025 orthophoto chips."""

from __future__ import annotations

import gzip
import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from fresh_urban_forest.classifier import (
    block_ids,
    classification_metrics,
    holdout_mask,
)
from fresh_urban_forest.imagery import TileSource, metro_2025_source
from fresh_urban_forest.terrain import project_lonlat
from train_imagery_classifier import SmallCNN, _augment

ROOT = Path("data/processed/surrey_2025")
OUT = Path("data/processed/imagery_classifier")
CACHE = Path("data/raw/imagery_cache/surrey_2025")
MODEL = OUT / "model.pt"
SIZE = 96
SAMPLE = 6000


def _prefetch(  # pragma: no cover - operator path
    source: TileSource,
    points: list[tuple[float, float]],
) -> None:
    coords: set[tuple[int, int]] = set()
    for lon, lat in points:
        gx, gy = source.global_pixel(lon, lat)
        left, top = gx - SIZE / 2.0, gy - SIZE / 2.0
        tx0, ty0 = math.floor(left / 256.0), math.floor(top / 256.0)
        tx1, ty1 = math.floor((left + SIZE - 1) / 256.0), math.floor((top + SIZE - 1) / 256.0)
        for tx in range(tx0, tx1 + 1):
            for ty in range(ty0, ty1 + 1):
                coords.add((tx, ty))
    print("prefetching", len(coords), "Surrey tiles", flush=True)
    with ThreadPoolExecutor(max_workers=32) as executor:
        futures = {executor.submit(source.tile, tx, ty): (tx, ty) for tx, ty in coords}
        for count, future in enumerate(as_completed(futures), start=1):
            try:
                future.result()
            except Exception as error:  # pragma: no cover - network path
                print("tile failed", futures[future], error, flush=True)
            if count % 1000 == 0:
                print("tiles", count, "/", len(coords), flush=True)


def _load_surrey() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    with gzip.open(ROOT / "map_trees.json.gz", "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    rows = [item for item in payload.get("features", []) if isinstance(item, dict)]
    conifer = [item for item in rows if item.get("properties", {}).get("group") == "conifer"]
    deciduous = [item for item in rows if item.get("properties", {}).get("group") == "deciduous"]
    rng = np.random.default_rng(20261106)
    rng.shuffle(conifer)
    rng.shuffle(deciduous)
    count = min(SAMPLE, len(conifer), len(deciduous))
    selected = conifer[:count] + deciduous[:count]
    labels = np.asarray([1] * count + [0] * count, dtype=np.uint8)
    points = [
        (
            float(item["geometry"]["coordinates"][0]),
            float(item["geometry"]["coordinates"][1]),
        )
        for item in selected
    ]
    source = metro_2025_source(CACHE)
    _prefetch(source, points)
    images = np.stack([source.chip(lon, lat, size=SIZE) for lon, lat in points], axis=0)
    x = np.asarray([project_lonlat(lon, lat, "EPSG:3157")[0] for lon, lat in points])
    y = np.asarray([project_lonlat(lon, lat, "EPSG:3157")[1] for lon, lat in points])
    return images, labels, x, y


def main() -> int:  # pragma: no cover - operator path
    """Fine-tune and evaluate the Surrey image model.

    Returns
    -------
    int
        Process status.
    """
    images, labels, x, y = _load_surrey()
    blocks = block_ids(x, y)
    held = holdout_mask(blocks)
    train, test = ~held, held
    device = torch.device("cuda")
    model = SmallCNN().to(device)
    model.load_state_dict(torch.load(MODEL, map_location=device, weights_only=True))
    counts = np.bincount(labels[train], minlength=2)
    weights = torch.tensor(
        [len(labels[train]) / (2.0 * max(int(count), 1)) for count in counts],
        dtype=torch.float32,
    ).to(device)
    criterion = nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    x_train = torch.from_numpy(images[train].transpose(0, 3, 1, 2).astype(np.float32) / 255.0)
    x_test = torch.from_numpy(images[test].transpose(0, 3, 1, 2).astype(np.float32) / 255.0)
    y_train = torch.from_numpy(labels[train].astype(np.int64))
    y_test = torch.from_numpy(labels[test].astype(np.int64))
    loader = DataLoader(TensorDataset(x_train, y_train), batch_size=64, shuffle=True)
    test_loader = DataLoader(TensorDataset(x_test, y_test), batch_size=256)
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
        probabilities = []
        truths = []
        with torch.no_grad():
            for batch_x, batch_y in test_loader:
                probabilities.append(
                    torch.softmax(model(batch_x.to(device)), dim=1)[:, 1].cpu().numpy()
                )
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
            torch.save(model.state_dict(), OUT / "surrey_model.pt")
    model.load_state_dict(
        torch.load(OUT / "surrey_model.pt", map_location=device, weights_only=True)
    )
    model.eval()
    probabilities = []
    truths = []
    with torch.no_grad():
        for batch_x, batch_y in test_loader:
            probabilities.append(
                torch.softmax(model(batch_x.to(device)), dim=1)[:, 1].cpu().numpy()
            )
            truths.append(batch_y.numpy())
    probability = np.concatenate(probabilities)
    truth = np.concatenate(truths).astype(np.bool_)
    metrics = classification_metrics(truth, probability >= 0.5, bootstrap=200)
    report = {
        "schema_version": "fresh-urban-forest.surrey-imagery-classifier.v1",
        "model_family": "Vancouver 2022 CNN fine-tuned on Surrey 2025 orthophoto chips",
        "source": "Metro Vancouver Orthophotos 2025",
        "zoom": 19,
        "chip_px": SIZE,
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
            "Imagery is 2025 and may not match every inventory measurement date.",
            "Coquitlam has no public species inventory.",
        ],
    }
    (OUT / "surrey_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("accuracy", metrics["accuracy"], "conifer", metrics["conifer"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
