#!/usr/bin/env python3
"""Train a GPU CNN on Vancouver orthophoto chips for conifer/deciduous screening."""

from __future__ import annotations

import argparse
import gzip
import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, cast

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
from fresh_urban_forest.imagery import TileSource, vancouver_2022_source
from fresh_urban_forest.terrain import project_lonlat

ROOT = Path("data/processed")
OUT = ROOT / "imagery_classifier"
CACHE = Path("data/raw/imagery_cache/vancouver_2022")
CHIP_SIZE = 96
SAMPLE_PER_CLASS = 6000
ZOOM = 19


class SmallCNN(nn.Module):
    """Small convolutional network for 96x96 RGB chips."""

    def __init__(self) -> None:  # pragma: no cover - operator path
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 32, 3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(128, 256, 3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d(1),
        )
        self.head = nn.Linear(256, 2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # pragma: no cover - operator path
        """Return class logits.

        Parameters
        ----------
        x : torch.Tensor
            ``(N, 3, 96, 96)`` RGB tensor.

        Returns
        -------
        torch.Tensor
            ``(N, 2)`` logits.
        """
        return cast("torch.Tensor", self.head(self.features(x).flatten(1)))


def _read_trees() -> list[dict[str, Any]]:  # pragma: no cover - operator path
    """Read Vancouver map-tree features."""
    with gzip.open(ROOT / "vancouver_2022" / "map_trees.json.gz", "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [item for item in payload.get("features", []) if isinstance(item, dict)]


def _points(  # pragma: no cover - operator path
    rows: list[dict[str, Any]],
) -> list[tuple[float, float]]:
    """Return WGS84 point coordinates."""
    return [
        (
            float(item["geometry"]["coordinates"][0]),
            float(item["geometry"]["coordinates"][1]),
        )
        for item in rows
    ]


def _prefetch(  # pragma: no cover - operator path
    source: TileSource,
    points: list[tuple[float, float]],
    *,
    size: int,
) -> None:
    """Prefetch all tiles needed for chips."""
    coords: set[tuple[int, int]] = set()
    for lon, lat in points:
        gx, gy = source.global_pixel(lon, lat)
        left, top = gx - size / 2.0, gy - size / 2.0
        tx0, ty0 = math.floor(left / 256.0), math.floor(top / 256.0)
        tx1, ty1 = math.floor((left + size - 1) / 256.0), math.floor((top + size - 1) / 256.0)
        for tx in range(tx0, tx1 + 1):
            for ty in range(ty0, ty1 + 1):
                coords.add((tx, ty))
    print(f"prefetching {len(coords)} orthophoto tiles", flush=True)
    completed = 0
    with ThreadPoolExecutor(max_workers=32) as executor:
        futures = {executor.submit(source.tile, tx, ty): (tx, ty) for tx, ty in coords}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as error:  # pragma: no cover - network path
                print(f"tile failed {futures[future]}: {error}", flush=True)
            completed += 1
            if completed % 500 == 0:
                print(f"tiles {completed}/{len(coords)}", flush=True)


def _build_dataset(  # pragma: no cover - operator path
    source: TileSource,
    points: list[tuple[float, float]],
) -> np.ndarray:
    """Build chips for points."""
    images = []
    for index, (lon, lat) in enumerate(points):
        images.append(source.chip(lon, lat, size=CHIP_SIZE))
        if (index + 1) % 1000 == 0:
            print(f"chips {index + 1}/{len(points)}", flush=True)
    return np.stack(images, axis=0)


def _load_or_build_dataset(  # pragma: no cover - operator path
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Load or build the Vancouver chip cache."""
    cache = OUT / "vancouver_chips.npz"
    if cache.is_file():
        payload = np.load(cache)
        return payload["images"], payload["labels"], payload["x"], payload["y"]
    rows = _read_trees()
    conifer = [item for item in rows if item.get("properties", {}).get("group") == "conifer"]
    deciduous = [item for item in rows if item.get("properties", {}).get("group") == "deciduous"]
    rng = np.random.default_rng(20261106)
    rng.shuffle(conifer)
    rng.shuffle(deciduous)
    count = min(SAMPLE_PER_CLASS, len(conifer), len(deciduous))
    selected = conifer[:count] + deciduous[:count]
    labels = np.asarray([1] * count + [0] * count, dtype=np.uint8)
    points = _points(selected)
    source = vancouver_2022_source(CACHE)
    _prefetch(source, points, size=CHIP_SIZE)
    images = _build_dataset(source, points)
    x = np.asarray([project_lonlat(lon, lat, "EPSG:3157")[0] for lon, lat in points])
    y = np.asarray([project_lonlat(lon, lat, "EPSG:3157")[1] for lon, lat in points])
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, images=images, labels=labels, x=x, y=y)
    return images, labels, x, y


def _augment(batch: torch.Tensor) -> torch.Tensor:  # pragma: no cover - operator path
    """Apply deterministic random flips to a CPU batch."""
    output = batch.clone()
    for index in range(output.shape[0]):
        if torch.rand(1).item() < 0.5:
            output[index] = torch.flip(output[index], dims=(2,))
        if torch.rand(1).item() < 0.5:
            output[index] = torch.flip(output[index], dims=(1,))
    return output


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - operator path
    """Train and evaluate the CNN.

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
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args(argv)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available")
    OUT.mkdir(parents=True, exist_ok=True)
    images, labels, x, y = _load_or_build_dataset()
    blocks = block_ids(x, y)
    held = holdout_mask(blocks)
    train = ~held
    test = held
    # Ensure both classes are present in the test set; otherwise keep the deterministic split.
    if len(np.unique(labels[test])) < 2:
        raise RuntimeError("test split lacks one class")
    x_train = torch.from_numpy(images[train].transpose(0, 3, 1, 2).astype(np.float32) / 255.0)
    x_test = torch.from_numpy(images[test].transpose(0, 3, 1, 2).astype(np.float32) / 255.0)
    y_train = torch.from_numpy(labels[train].astype(np.int64))
    y_test = torch.from_numpy(labels[test].astype(np.int64))
    device = torch.device("cuda")
    model = SmallCNN().to(device)
    counts = np.bincount(labels[train], minlength=2)
    weights = torch.tensor(
        [len(labels[train]) / (2.0 * max(int(count), 1)) for count in counts],
        dtype=torch.float32,
    ).to(device)
    criterion = nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    train_loader = DataLoader(
        TensorDataset(x_train, y_train),
        batch_size=args.batch_size,
        shuffle=True,
    )
    test_loader = DataLoader(TensorDataset(x_test, y_test), batch_size=256)
    best_accuracy = -1.0
    history: list[dict[str, float]] = []
    for epoch in range(1, args.epochs + 1):
        model.train()
        running = 0.0
        seen = 0
        for batch_x, batch_y in train_loader:
            batch_x = _augment(batch_x).to(device, non_blocking=True)
            batch_y = batch_y.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            logits = model(batch_x)
            loss = criterion(logits, batch_y)
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
        predicted = probability >= 0.5
        accuracy = float(np.mean(predicted == truth))
        history.append({"epoch": epoch, "loss": running / max(seen, 1), "accuracy": accuracy})
        print(
            f"epoch {epoch}: loss {running / max(seen, 1):.3f} accuracy {accuracy:.4f}",
            flush=True,
        )
        if accuracy > best_accuracy:
            best_accuracy = accuracy
            torch.save(model.state_dict(), OUT / "model.pt")
    model.load_state_dict(torch.load(OUT / "model.pt", map_location=device, weights_only=True))
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
    predictions = probability >= 0.5
    metrics = classification_metrics(truth, predictions, bootstrap=200)
    metrics["brier_score"] = brier_score(probability, truth)
    metrics["calibration"] = calibration_table(probability, truth)
    report = {
        "schema_version": "fresh-urban-forest.imagery-classifier.v1",
        "model_family": "small 4-block CNN, 96x96 RGB orthophoto chips",
        "source": "City of Vancouver Orthophotos 2022 tiled service",
        "source_url": "https://tiles.arcgis.com/tiles/qrcTTRTwUoS8N47o/arcgis/rest/services/Orthophotos_2022/MapServer",
        "zoom": ZOOM,
        "chip_px": CHIP_SIZE,
        "sample_per_class": SAMPLE_PER_CLASS,
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
            "Vancouver public inventory labels are known-good relative to the inventory.",
            "Orthophoto date 2022; tree inventory heights may be measured or imputed.",
            "No stereo photogrammetry: these are orthorectified tiles.",
            "Burnaby/Coquitlam still lack public species labels.",
        ],
    }
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    accuracy_value: object = metrics["accuracy"]
    conifer_metrics = metrics["conifer"]
    precision_value: object = (
        conifer_metrics["precision"] if isinstance(conifer_metrics, dict) else 0.0
    )
    if isinstance(accuracy_value, (int, float)) and isinstance(precision_value, (int, float)):
        print(
            f"accuracy {float(accuracy_value):.4f}; conifer precision {float(precision_value):.4f}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
