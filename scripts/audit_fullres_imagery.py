#!/usr/bin/env python3
"""Compare full-resolution and 0.30 m image scores on the same candidates."""

from __future__ import annotations

import argparse
import csv
import gzip
import itertools
import json
from pathlib import Path
from typing import Any, cast

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

from fresh_urban_forest.fullres_imagery import FullResolutionSource
from fresh_urban_forest.terrain import project_lonlat
from train_imagery_classifier import SmallCNN

ROOT = Path("data/processed/surrey_2025")
OUT = ROOT / "fullres_audit"
FULLRES_MODEL = Path("data/processed/imagery_classifier/fullres_surrey_model.pt")
BASE_MODEL = Path("data/processed/imagery_classifier/model.pt")
FULLRES_CHIP = 128
AUDIT_CHIP = 384
BASE_CHIP = 96


def _features() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with gzip.open(ROOT / "off_inventory.geojson.gz", "rt", encoding="utf-8") as handle:
        collection = json.load(handle)
    rows: list[dict[str, Any]] = [
        cast("dict[str, Any]", item)
        for item in collection["features"]
        if float(item["properties"]["confidence"]) >= 0.6
    ]
    return cast("dict[str, Any]", collection), rows


def _stratified(rows: list[dict[str, Any]], *, per_bin: int) -> list[int]:
    probabilities = np.asarray(
        [float(item["properties"]["image_conifer_probability"]) for item in rows],
        dtype=np.float64,
    )
    edges = np.linspace(0.0, 1.0, 11)
    rng = np.random.default_rng(20261107)
    selected: list[int] = []
    for low, high in itertools.pairwise(edges):
        candidates = np.where(
            (probabilities >= low) & (probabilities < high if high < 1.0 else probabilities <= high)
        )[0]
        if len(candidates) == 0:
            continue
        take = min(per_bin, len(candidates))
        selected.extend(int(index) for index in rng.choice(candidates, take, replace=False))
    return selected


def _infer(
    model_path: Path,
    images: np.ndarray,
    *,
    device: torch.device,
) -> np.ndarray:
    model = SmallCNN().to(device)
    model.load_state_dict(torch.load(model_path, map_location=device, weights_only=True))
    model.eval()
    output: list[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(images), 128):
            batch = images[start : start + 128].transpose(0, 3, 1, 2).astype(np.float32) / 255.0
            tensor = torch.from_numpy(batch).to(device)
            output.append(torch.softmax(model(tensor), dim=1)[:, 1].cpu().numpy())
    return np.concatenate(output)


def _contact_sheet(
    items: list[tuple[int, np.ndarray]],
    path: Path,
    *,
    columns: int = 5,
) -> None:
    rows = (len(items) + columns - 1) // columns
    cell = AUDIT_CHIP + 28
    sheet = Image.new("RGB", (columns * cell, rows * cell), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=18)
    for offset, (index, chip) in enumerate(items):
        col = offset % columns
        row = offset // columns
        image = Image.fromarray(chip, mode="RGB")
        px = col * cell + (cell - AUDIT_CHIP) // 2
        py = row * cell + 24
        sheet.paste(image, (px, py))
        cx = px + AUDIT_CHIP // 2
        cy = py + AUDIT_CHIP // 2
        draw.line((cx - 10, cy, cx + 10, cy), fill=(255, 30, 30), width=2)
        draw.line((cx, cy - 10, cx, cy + 10), fill=(255, 30, 30), width=2)
        draw.text((col * cell + 4, row * cell + 3), f"#{index}", fill="black", font=font)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, quality=92)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - operator path
    """Run the same-point scale comparison and build the audit packet.

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
    parser.add_argument("--per-bin", type=int, default=100)
    parser.add_argument("--audit-per-bin", type=int, default=20)
    args = parser.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    _collection, rows = _features()
    selected = _stratified(rows, per_bin=args.per_bin)
    print("comparison sample", len(selected), flush=True)
    source = FullResolutionSource(ROOT / "fullres.vrt", chip_px=AUDIT_CHIP)
    points: list[tuple[float, float]] = [
        project_lonlat(
            float(rows[index]["geometry"]["coordinates"][0]),
            float(rows[index]["geometry"]["coordinates"][1]),
            "EPSG:3157",
        )
        for index in selected
    ]
    xy = np.asarray(points, dtype=np.float64)
    wide = np.empty((len(selected), AUDIT_CHIP, AUDIT_CHIP, 3), dtype=np.uint8)
    for offset, (x, y) in enumerate(xy):
        wide[offset] = source.chip(float(x), float(y), size=AUDIT_CHIP)
        if (offset + 1) % 200 == 0:
            print("wide chips", offset + 1, "/", len(selected), flush=True)
    source.close()
    centre = (AUDIT_CHIP - FULLRES_CHIP) // 2
    fullres_images = wide[:, centre : centre + FULLRES_CHIP, centre : centre + FULLRES_CHIP]
    base_images = np.stack(
        [
            np.asarray(
                Image.fromarray(image).resize((BASE_CHIP, BASE_CHIP), Image.Resampling.BILINEAR)
            )
            for image in wide
        ],
        axis=0,
    )
    device = torch.device("cuda")
    p_full = _infer(FULLRES_MODEL, fullres_images, device=device)
    p_base = _infer(BASE_MODEL, base_images, device=device)
    saved_full = np.asarray(
        [float(rows[index]["properties"]["image_conifer_probability"]) for index in selected],
        dtype=np.float64,
    )
    with (OUT / "comparison.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "candidate_index",
                "candidate_id",
                "p_fullres_saved",
                "p_fullres_recomputed",
                "p_030_downsampled",
                "fullres_group",
                "scale03_group",
            ]
        )
        for index, saved, full, base in zip(selected, saved_full, p_full, p_base, strict=True):
            properties = rows[index]["properties"]
            writer.writerow(
                [
                    index,
                    properties.get("candidate_id", properties.get("id", index)),
                    f"{saved:.6f}",
                    f"{float(full):.6f}",
                    f"{float(base):.6f}",
                    "conifer" if full >= 0.5 else "deciduous",
                    "conifer" if base >= 0.5 else "deciduous",
                ]
            )
    agreement = float(np.mean((p_full >= 0.5) == (p_base >= 0.5)))
    correlation = float(np.corrcoef(p_full, p_base)[0, 1])
    comparison = {
        "sample": len(selected),
        "fullres_conifer_share": float(np.mean(p_full >= 0.5)),
        "scale03_conifer_share": float(np.mean(p_base >= 0.5)),
        "agreement_at_0_5": agreement,
        "correlation": correlation,
        "mean_p_fullres": float(p_full.mean()),
        "mean_p_030": float(p_base.mean()),
        "mean_difference": float((p_full - p_base).mean()),
        "median_difference": float(np.median(p_full - p_base)),
        "saved_vs_recomputed_mad": float(np.mean(np.abs(saved_full - p_full))),
        "comparison_note": (
            "The 0.30 m comparison chip is a 96 px bilinear downsample of the same 28.8 m "
            "full-resolution crop, not the City service image. The full-resolution model "
            "uses its native 128 px / 9.6 m chip."
        ),
    }
    (OUT / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    audit_indices: list[int] = []
    all_probabilities = np.asarray(
        [float(rows[index]["properties"]["image_conifer_probability"]) for index in selected],
        dtype=np.float64,
    )
    for low, high in itertools.pairwise(np.linspace(0.0, 1.0, 11)):
        in_bin = [
            index
            for index, probability in zip(selected, all_probabilities, strict=True)
            if low <= probability < high
        ]
        audit_indices.extend(in_bin[: args.audit_per_bin])
    with (OUT / "audit_key.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "candidate_index",
                "candidate_id",
                "page",
                "p_fullres",
                "p_030",
                "human_group",
                "confidence",
                "notes",
            ]
        )
        for offset, index in enumerate(audit_indices):
            row = selected.index(index)
            properties = rows[index]["properties"]
            writer.writerow(
                [
                    index,
                    properties.get("candidate_id", properties.get("id", index)),
                    offset // 20 + 1,
                    f"{float(p_full[row]):.6f}",
                    f"{float(p_base[row]):.6f}",
                    "",
                    "",
                    "",
                ]
            )
    for page_start in range(0, len(audit_indices), 20):
        items = [
            (index, wide[selected.index(index)])
            for index in audit_indices[page_start : page_start + 20]
        ]
        _contact_sheet(items, OUT / f"audit_page_{page_start // 20 + 1:02d}.jpg")
    print(json.dumps(comparison, indent=2), flush=True)
    print("audit pages", (len(audit_indices) + 19) // 20, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
