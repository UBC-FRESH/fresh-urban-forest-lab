"""Tests for the Vancouver action-screen build script."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from build_vancouver_action_screen import build_product, load_cells, parse_args

CRS = "EPSG:3157"
BOUNDS = [0.0, 0.0, 800.0, 400.0]


def _cells() -> list[dict[str, object]]:
    """Return two synthetic P38/P39/P40 cells."""
    return [
        {
            "cell_id": "r00c00",
            "row": 0,
            "col": 0,
            "bounds": [0.0, 0.0, 400.0, 400.0],
            "shade_deficit": 0.8,
            "equity_score": 0.7,
            "priority_class": "1A",
            "gap_m2": 5000.0,
            "street_gap_m2": 1000.0,
            "opportunity_tier": "high",
            "lst_mean_c": 42.0,
            "tespi_like": 0.9,
            "heat_equity_tier": "high",
        },
        {
            "cell_id": "r00c01",
            "row": 0,
            "col": 1,
            "bounds": [400.0, 0.0, 800.0, 400.0],
            "shade_deficit": 0.2,
            "equity_score": 0.2,
            "priority_class": "4B",
            "gap_m2": 100.0,
            "street_gap_m2": 0.0,
            "opportunity_tier": "low",
            "lst_mean_c": 30.0,
            "tespi_like": 0.2,
            "heat_equity_tier": "low",
        },
    ]


def _make_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Write four small product files."""
    cells = _cells()
    paths = [tmp_path / name for name in ("p38.json", "p39.json", "p40.json")]
    for path in paths:
        path.write_text(
            json.dumps({"metadata": {"crs": CRS, "bounds": BOUNDS}, "cells": cells}),
            encoding="utf-8",
        )
    change = tmp_path / "p41.json"
    change.write_text(
        json.dumps(
            {
                "metadata": {"crs": CRS},
                "cells": [
                    {
                        "cell_id": "r00c00",
                        "change_class": "loss",
                        "net_m2": -10.0,
                        "gain_m2": 0.0,
                        "loss_m2": 10.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return paths[0], paths[1], paths[2], change


def test_parse_args_defaults() -> None:
    """The default output is the Vancouver product directory."""
    args = parse_args([])
    assert args.out.name == "vancouver_2022"


def test_load_cells_requires_product(tmp_path: Path) -> None:
    """A missing product is an explicit error."""
    with pytest.raises(FileNotFoundError):
        load_cells(tmp_path / "missing.json")


def test_build_product_writes_products(tmp_path: Path) -> None:
    """The build writes JSON, GeoJSON, PNG, and metadata."""
    p38, p39, p40, p41 = _make_inputs(tmp_path)
    out = tmp_path / "out"
    result = build_product(
        priority_path=p38,
        planting_path=p39,
        heat_path=p40,
        change_path=p41,
        out_dir=out,
    )
    assert cast("int", result["cell_count"]) == 2
    counts = cast("dict[str, int]", result["action_counts"])
    assert counts["protect_loss"] == 1
    assert (out / "canopy_action.json").exists()
    assert (out / "canopy_action.geojson").exists()
    assert (out / "canopy_action.png").exists()
    assert (out / "canopy_action_meta.json").exists()
    payload = json.loads((out / "canopy_action.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "fresh-urban-forest.canopy-action.v1"
