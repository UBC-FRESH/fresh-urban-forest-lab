#!/usr/bin/env python3
"""Fuse image CNN probabilities with independent CHM crown features."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

from fresh_urban_forest.classifier import (
    block_ids,
    classification_metrics,
    fit_logistic,
    holdout_mask,
)
from fresh_urban_forest.crown_features import FEATURE_NAMES as CHM_FEATURE_NAMES
from fresh_urban_forest.crown_features import crown_features
from fresh_urban_forest.terrain import read_raster
from train_imagery_classifier import SmallCNN

OUT = Path("data/processed/imagery_classifier")
CHM = Path("data/processed/vancouver_2022/chm.tif")


def main() -> int:  # pragma: no cover - operator path
    """Train and evaluate image, CHM, and fused models.

    Returns
    -------
    int
        Process status.
    """
    payload = np.load(OUT / "vancouver_chips.npz")
    images = payload["images"]
    labels = payload["labels"].astype(np.bool_)
    x = payload["x"]
    y = payload["y"]
    blocks = block_ids(x, y)
    held = holdout_mask(blocks)
    train = ~held
    test = held
    chm = read_raster(CHM)
    chm_values = np.asarray(
        [crown_features(chm, float(px), float(py)).values for px, py in zip(x, y, strict=True)],
        dtype=np.float64,
    )
    device = torch.device("cuda")
    model = SmallCNN().to(device)
    model.load_state_dict(torch.load(OUT / "model.pt", map_location=device, weights_only=True))
    model.eval()
    tensor = torch.from_numpy(images.transpose(0, 3, 1, 2).astype(np.float32) / 255.0)
    loader = DataLoader(TensorDataset(tensor), batch_size=256)
    probabilities: list[np.ndarray] = []
    with torch.no_grad():
        for (batch,) in loader:
            probabilities.append(torch.softmax(model(batch.to(device)), dim=1)[:, 1].cpu().numpy())
    image_probability = np.concatenate(probabilities)
    image_metrics = classification_metrics(
        labels[test],
        image_probability[test] >= 0.5,
        bootstrap=200,
    )
    chm_model = fit_logistic(
        chm_values[train],
        labels[train],
        feature_names=CHM_FEATURE_NAMES,
    )
    chm_metrics = classification_metrics(
        labels[test], chm_model.predict_proba(chm_values[test]) >= 0.5, bootstrap=200
    )
    fused_values = np.column_stack((chm_values, image_probability))
    fused_model = fit_logistic(
        fused_values[train],
        labels[train],
        feature_names=(*CHM_FEATURE_NAMES, "image_probability"),
    )
    fused_probability = fused_model.predict_proba(fused_values[test])
    fused_metrics = classification_metrics(labels[test], fused_probability >= 0.5, bootstrap=200)
    report = {
        "schema_version": "fresh-urban-forest.lidar-image-fusion.v1",
        "image_model": {"evaluation": image_metrics},
        "chm_model": {
            "features": list(CHM_FEATURE_NAMES),
            "evaluation": chm_metrics,
        },
        "fused_model": {
            "features": list(fused_model.feature_names),
            "coefficients": [float(value) for value in fused_model.coefficients],
            "intercept": float(fused_model.intercept),
            "evaluation": fused_metrics,
        },
        "training": {
            "rows": len(labels),
            "train_rows": int(train.sum()),
            "test_rows": int(test.sum()),
            "spatial_block_m": 500,
        },
        "validity": (
            "CHM features are independent of inventory species labels; image probabilities "
            "come from a CNN trained on the training split. This is a valid held-out fusion."
        ),
        "caveats": [
            "Vancouver labels are known-good relative to inventory, not field audited.",
            "Training/test are spatially blocked.",
            "Image and CHM features are both remote-sensing-derived.",
        ],
    }
    (OUT / "fusion_chm_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    for name, metrics in (
        ("image", image_metrics),
        ("chm", chm_metrics),
        ("fused", fused_metrics),
    ):
        print(name, "accuracy", metrics["accuracy"])
        print(name, "conifer", metrics["conifer"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
