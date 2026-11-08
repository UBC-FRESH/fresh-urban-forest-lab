"""Tests for the change-cell build script."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import numpy as np

from build_vancouver_change_cells import (
    build_product,
    load_cells,
    parse_args,
)

CRS = "EPSG:3157"
BOUNDS = (0.0, 0.0, 4.0, 4.0)


def _make_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Create a 4 by 4 change product and three lookup products."""
    change_dir = tmp_path / "change"
    change_dir.mkdir()
    earlier = np.zeros((4, 4), dtype=np.float32)
    later = np.zeros((4, 4), dtype=np.float32)
    earlier[0:2, :] = 5.0
    later[0:2, :] = 5.0
    later[3, 0] = 5.0
    valid = np.ones((4, 4), dtype=np.bool_)
    np.savez_compressed(
        change_dir / "change_grid.npz",
        earlier=earlier,
        later=later,
        valid=valid,
        change=np.zeros((4, 4), dtype=np.int8),
    )
    (change_dir / "change.json").write_text(
        json.dumps(
            {
                "earlier_label": "2018",
                "later_label": "2022",
                "crs": CRS,
                "bounds": list(BOUNDS),
                "valid_overlap_m2": 16.0,
                "metrics": {"net_m2": 4.0},
            }
        ),
        encoding="utf-8",
    )
    lookup = {
        "metadata": {"bounds": list(BOUNDS), "crs": CRS},
        "cells": [{"cell_id": "r00c00", "shade_deficit": 0.8, "equity_score": 0.7}],
    }
    p38 = tmp_path / "p38.json"
    p39 = tmp_path / "p39.json"
    p40 = tmp_path / "p40.json"
    p38.write_text(json.dumps(lookup), encoding="utf-8")
    p39.write_text(
        json.dumps({"cells": [{"cell_id": "r00c00", "gap_m2": 100.0, "opportunity_tier": "high"}]}),
        encoding="utf-8",
    )
    p40.write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "cell_id": "r00c00",
                        "lst_mean_c": 40.0,
                        "tespi_like": 0.8,
                        "heat_equity_tier": "high",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return change_dir, p38, p39, p40


def test_parse_args_defaults() -> None:
    """The script defaults to the downtown change directory."""
    args = parse_args([])
    assert args.change_dir.name == "change_vancouver_2018_2022_downtown"
    assert args.cell_size == 400.0


def test_load_cells_handles_missing_file(tmp_path: Path) -> None:
    """A missing product is treated as an empty optional join."""
    assert load_cells(tmp_path / "missing.json") == {}


def test_build_product_writes_products(tmp_path: Path) -> None:
    """The build writes JSON, GeoJSON, PNG, and metadata."""
    change_dir, p38, p39, p40 = _make_inputs(tmp_path)
    out = tmp_path / "out"
    result = build_product(
        change_dir=change_dir,
        heat_priority=p38,
        planting=p39,
        heat_equity=p40,
        out_dir=out,
        threshold_m=1.0,
        cell_size_m=4.0,
    )
    assert cast("int", result["cell_count"]) == 1
    assert (out / "canopy_change.json").exists()
    assert (out / "canopy_change.geojson").exists()
    assert (out / "canopy_change.png").exists()
    assert (out / "canopy_change_meta.json").exists()
    payload = json.loads((out / "canopy_change.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "fresh-urban-forest.canopy-change.v1"
    assert payload["cells"][0]["heat_equity_tier"] == "high"
