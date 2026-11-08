"""Tests for the Vancouver turnover build script."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import numpy as np

from build_vancouver_turnover import build_product, parse_args


def _make_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    """Create a tiny change product and four lookups."""
    change = tmp_path / "change"
    change.mkdir()
    classes = np.zeros((4, 4), dtype=np.int8)
    classes[0, 0:2] = -1
    classes[2, 2:4] = 1
    np.savez_compressed(
        change / "change_grid.npz",
        change=classes,
        earlier=np.zeros((4, 4), dtype=np.float32),
        later=np.zeros((4, 4), dtype=np.float32),
        valid=np.ones((4, 4), dtype=np.bool_),
    )
    (change / "change.json").write_text(
        json.dumps({"crs": "EPSG:3157", "bounds": [0.0, 0.0, 4.0, 4.0]}),
        encoding="utf-8",
    )
    paths = [tmp_path / name for name in ("p38.json", "p39.json", "p40.json", "p42.json")]
    for path in paths:
        path.write_text(
            json.dumps(
                {
                    "metadata": {"bounds": [0.0, 0.0, 4.0, 4.0]},
                    "cells": [
                        {
                            "cell_id": "r00c00",
                            "shade_deficit": 0.8,
                            "equity_score": 0.7,
                            "gap_m2": 100.0,
                            "opportunity_tier": "high",
                            "lst_mean_c": 40.0,
                            "heat_equity_tier": "high",
                            "action_class": "plant_cool",
                            "action_label": "plant + cool",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
    return change, paths[0], paths[1], paths[2], paths[3]


def test_parse_args_defaults() -> None:
    """The default minimum patch is 50 m²."""
    args = parse_args([])
    assert args.min_patch == 50.0


def test_build_product_writes_files(tmp_path: Path) -> None:
    """The build writes JSON, GeoJSON, PNG, and metadata."""
    change, p38, p39, p40, p42 = _make_inputs(tmp_path)
    out = tmp_path / "out"
    result = build_product(
        change_dir=change,
        priority=p38,
        planting=p39,
        heat=p40,
        action=p42,
        out_dir=out,
        min_patch_m2=1.0,
        cell_size_m=4.0,
    )
    assert cast("int", result["cell_count"]) == 1
    assert (out / "canopy_turnover.json").exists()
    assert (out / "canopy_turnover.geojson").exists()
    assert (out / "canopy_turnover.png").exists()
    payload = json.loads((out / "canopy_turnover.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "fresh-urban-forest.canopy-turnover.v1"
