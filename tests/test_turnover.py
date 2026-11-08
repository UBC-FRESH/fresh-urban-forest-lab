"""Tests for canopy turnover hotspots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import numpy as np
import pytest

from fresh_urban_forest.turnover import (
    TURNOVER_EVIDENCE,
    build_turnover_cells,
    turnover_geojson,
    turnover_png,
    write_turnover_product,
)


def _change() -> tuple[np.ndarray, np.ndarray]:
    """Return a tiny gain/loss change fixture."""
    change = np.zeros((4, 4), dtype=np.int8)
    change[0, 0:2] = -1
    change[2, 2:4] = 1
    valid = np.ones((4, 4), dtype=np.bool_)
    return change, valid


def test_turnover_counts_patches_and_joins() -> None:
    """The cell reports gain/loss patches and optional joins."""
    change, valid = _change()
    cells = build_turnover_cells(
        change=change,
        valid=valid,
        change_bounds=(0.0, 0.0, 4.0, 4.0),
        grid_bounds=(0.0, 0.0, 4.0, 4.0),
        crs="EPSG:3157",
        min_patch_m2=1.0,
        cell_size_m=4.0,
        priority={"r00c00": {"shade_deficit": 0.8, "equity_score": 0.7}},
        planting={"r00c00": {"gap_m2": 100.0, "opportunity_tier": "high"}},
        heat={"r00c00": {"lst_mean_c": 40.0, "heat_equity_tier": "high"}},
        action={"r00c00": {"action_class": "plant_cool", "action_label": "plant + cool"}},
    )
    assert len(cells) == 1
    cell = cells[0]
    assert cell.gain_patch_count == 1
    assert cell.loss_patch_count == 1
    assert cell.turnover_area_m2 == pytest.approx(4.0)
    assert cell.largest_gain_patch_m2 == pytest.approx(2.0)
    assert cell.largest_loss_patch_m2 == pytest.approx(2.0)
    assert cell.action_class == "plant_cool"


def test_turnover_min_patch_filters_small_components() -> None:
    """A patch below the minimum is not counted."""
    change, valid = _change()
    cells = build_turnover_cells(
        change=change,
        valid=valid,
        change_bounds=(0.0, 0.0, 4.0, 4.0),
        grid_bounds=(0.0, 0.0, 4.0, 4.0),
        crs="EPSG:3157",
        min_patch_m2=5.0,
        cell_size_m=4.0,
    )
    assert cells[0].gain_patch_count == 0
    assert cells[0].loss_patch_count == 0


def test_turnover_rejects_bad_inputs() -> None:
    """Shape and parameter errors are explicit."""
    change, valid = _change()
    with pytest.raises(ValueError, match="share a 2-D shape"):
        build_turnover_cells(
            change=change,
            valid=np.ones((3, 4), dtype=np.bool_),
            change_bounds=(0.0, 0.0, 4.0, 4.0),
            grid_bounds=(0.0, 0.0, 4.0, 4.0),
            crs="EPSG:3157",
        )
    with pytest.raises(ValueError, match="positive"):
        build_turnover_cells(
            change=change,
            valid=valid,
            change_bounds=(0.0, 0.0, 4.0, 4.0),
            grid_bounds=(0.0, 0.0, 4.0, 4.0),
            crs="EPSG:3157",
            min_patch_m2=0.0,
        )


def test_turnover_exports(tmp_path: Path) -> None:
    """GeoJSON is WGS84 and PNG/product files are written."""
    change, valid = _change()
    cells = build_turnover_cells(
        change=change,
        valid=valid,
        change_bounds=(0.0, 0.0, 4.0, 4.0),
        grid_bounds=(0.0, 0.0, 4.0, 4.0),
        crs="EPSG:3157",
        min_patch_m2=1.0,
        cell_size_m=4.0,
    )
    collection = turnover_geojson(cells, crs="EPSG:3157", metadata={"method": "test"})
    features = cast("list[dict[str, object]]", collection["features"])
    geometry = cast("dict[str, object]", features[0]["geometry"])
    coordinates = cast("list[list[list[float]]]", geometry["coordinates"])[0][0]
    assert -180.0 <= coordinates[0] <= 180.0
    assert -90.0 <= coordinates[1] <= 90.0
    assert turnover_png(cells).startswith(b"\x89PNG")
    paths = write_turnover_product(
        cells,
        tmp_path,
        crs="EPSG:3157",
        metadata={"method": "test", "evidence": TURNOVER_EVIDENCE.to_dict()},
    )
    assert paths["json"].exists()
    assert paths["geojson"].exists()
    assert paths["png"].exists()
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == "fresh-urban-forest.canopy-turnover.v1"
