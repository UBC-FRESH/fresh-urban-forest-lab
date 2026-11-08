"""Tests for the integrated canopy-action screen."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from fresh_urban_forest.action_screen import (
    ACTION_EVIDENCE,
    action_geojson,
    action_png,
    build_action_cells,
    write_action_product,
)


def _inputs() -> tuple[
    dict[str, dict[str, object]],
    dict[str, dict[str, object]],
    dict[str, dict[str, object]],
    dict[str, dict[str, object]],
]:
    """Return two cells with contrasting heat/gap states."""
    bounds = [0.0, 0.0, 400.0, 400.0]
    priority = {
        "r00c00": {
            "cell_id": "r00c00",
            "row": 0,
            "col": 0,
            "bounds": bounds,
            "shade_deficit": 0.8,
            "equity_score": 0.7,
            "priority_class": "1A",
        },
        "r00c01": {
            "cell_id": "r00c01",
            "row": 0,
            "col": 1,
            "bounds": [400.0, 0.0, 800.0, 400.0],
            "shade_deficit": 0.2,
            "equity_score": 0.2,
            "priority_class": "4B",
        },
    }
    planting = {
        "r00c00": {
            "cell_id": "r00c00",
            "gap_m2": 5000.0,
            "street_gap_m2": 2000.0,
            "opportunity_tier": "high",
        },
        "r00c01": {
            "cell_id": "r00c01",
            "gap_m2": 100.0,
            "street_gap_m2": 0.0,
            "opportunity_tier": "low",
        },
    }
    heat = {
        "r00c00": {
            "cell_id": "r00c00",
            "lst_mean_c": 42.0,
            "tespi_like": 0.9,
            "heat_equity_tier": "high",
        },
        "r00c01": {
            "cell_id": "r00c01",
            "lst_mean_c": 30.0,
            "tespi_like": 0.2,
            "heat_equity_tier": "low",
        },
    }
    change = {
        "r00c00": {
            "cell_id": "r00c00",
            "change_class": "loss",
            "net_m2": -10.0,
            "gain_m2": 0.0,
            "loss_m2": 10.0,
        },
    }
    return priority, planting, heat, change


def test_action_matrix_assigns_plant_protect_and_monitor() -> None:
    """Loss overrides, high/high becomes plant/cool, low/low becomes monitor."""
    priority, planting, heat, change = _inputs()
    cells = build_action_cells(
        priority=priority, planting=planting, heat=heat, change=change, crs="EPSG:3157"
    )
    assert len(cells) == 2
    by_id = {cell.cell_id: cell for cell in cells}
    assert by_id["r00c00"].action_class == "protect_loss"
    assert by_id["r00c00"].change_observed
    assert not by_id["r00c01"].change_observed
    assert by_id["r00c01"].change_class == "not observed"
    assert by_id["r00c01"].action_class == "monitor"


def test_high_heat_low_gap_becomes_structural_shade() -> None:
    """A hot cell without a large gap gets structural shade."""
    priority, planting, heat, _change = _inputs()
    planting["r00c00"]["gap_m2"] = 0.0
    planting["r00c00"]["opportunity_tier"] = "low"
    heat["r00c00"]["heat_equity_tier"] = "high"
    cells = build_action_cells(
        priority=priority, planting=planting, heat=heat, change={}, crs="EPSG:3157"
    )
    by_id = {cell.cell_id: cell for cell in cells}
    assert by_id["r00c00"].action_class == "structural_shade"


def test_action_screen_requires_cells() -> None:
    """No joined cells is an error."""
    with pytest.raises(ValueError, match="no P38"):
        build_action_cells(priority={}, planting={}, heat={}, change={}, crs="EPSG:3157")


def test_action_geojson_png_and_product(tmp_path: Path) -> None:
    """Exports produce WGS84 GeoJSON, PNG, and JSON."""
    priority, planting, heat, change = _inputs()
    cells = build_action_cells(
        priority=priority, planting=planting, heat=heat, change=change, crs="EPSG:3157"
    )
    collection = action_geojson(cells, crs="EPSG:3157", metadata={"method": "test"})
    features = cast("list[dict[str, object]]", collection["features"])
    geometry = cast("dict[str, object]", features[0]["geometry"])
    coordinates = cast("list[list[list[float]]]", geometry["coordinates"])[0][0]
    assert -180.0 <= coordinates[0] <= 180.0
    assert -90.0 <= coordinates[1] <= 90.0
    assert action_png(cells).startswith(b"\x89PNG")
    paths = write_action_product(
        cells,
        tmp_path,
        crs="EPSG:3157",
        metadata={"method": "test", "evidence": ACTION_EVIDENCE.to_dict()},
    )
    assert paths["json"].exists()
    assert paths["geojson"].exists()
    assert paths["png"].exists()
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == "fresh-urban-forest.canopy-action.v1"
