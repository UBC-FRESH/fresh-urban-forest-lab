"""Tests for observed canopy-change cells."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import numpy as np
import pytest

from fresh_urban_forest.change_cells import (
    CHANGE_CELL_EVIDENCE,
    build_change_cells,
    change_cells_geojson,
    change_cells_png,
    write_change_cells,
)


def _arrays() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return a 4 by 4 change fixture with gain, loss, and stable canopy."""
    earlier = np.zeros((4, 4), dtype=np.float32)
    later = np.zeros((4, 4), dtype=np.float32)
    earlier[0:2, :] = 5.0
    later[0:2, :] = 5.0
    earlier[2, 0] = 5.0
    later[2, 0] = 0.0
    later[3, 0] = 5.0
    valid = np.ones((4, 4), dtype=np.bool_)
    return earlier, later, valid


def test_build_change_cells_reports_gain_loss_and_join() -> None:
    """The cell reports areas and joins the optional screening fields."""
    earlier, later, valid = _arrays()
    cells = build_change_cells(
        earlier=earlier,
        later=later,
        valid=valid,
        change_bounds=(0.0, 0.0, 4.0, 4.0),
        grid_bounds=(0.0, 0.0, 4.0, 4.0),
        crs="EPSG:3157",
        threshold_m=1.0,
        cell_size_m=4.0,
        priority={"r00c00": {"shade_deficit": 0.8, "equity_score": 0.7, "priority_class": "1A"}},
        planting={"r00c00": {"gap_m2": 100.0, "opportunity_tier": "high"}},
        heat={"r00c00": {"lst_mean_c": 40.0, "tespi_like": 0.8, "heat_equity_tier": "high"}},
    )
    assert len(cells) == 1
    cell = cells[0]
    assert cell.earlier_canopy_m2 == pytest.approx(9.0)
    assert cell.later_canopy_m2 == pytest.approx(9.0)
    assert cell.gain_m2 == pytest.approx(1.0)
    assert cell.loss_m2 == pytest.approx(1.0)
    assert cell.stable_m2 == pytest.approx(8.0)
    assert cell.net_m2 == pytest.approx(0.0)
    assert cell.mean_height_change_m == pytest.approx(0.0)
    assert cell.p38_priority_class == "1A"
    assert cell.opportunity_tier == "high"
    assert cell.heat_equity_tier == "high"


def test_change_cell_is_gain_when_net_exceeds_five_percent() -> None:
    """A net increase above five percent is classed as gain."""
    earlier = np.zeros((2, 2), dtype=np.float32)
    later = np.ones((2, 2), dtype=np.float32) * 10.0
    valid = np.ones((2, 2), dtype=np.bool_)
    cells = build_change_cells(
        earlier=earlier,
        later=later,
        valid=valid,
        change_bounds=(0.0, 0.0, 2.0, 2.0),
        grid_bounds=(0.0, 0.0, 2.0, 2.0),
        crs="EPSG:3157",
        threshold_m=1.0,
        cell_size_m=2.0,
    )
    assert cells[0].change_class == "gain"


def test_build_change_cells_rejects_bad_shape_and_cell_size() -> None:
    """Mismatched arrays and non-positive cell sizes are rejected."""
    earlier, later, valid = _arrays()
    with pytest.raises(ValueError, match="share a 2-D shape"):
        build_change_cells(
            earlier=earlier,
            later=later,
            valid=np.ones((3, 4), dtype=np.bool_),
            change_bounds=(0.0, 0.0, 4.0, 4.0),
            grid_bounds=(0.0, 0.0, 4.0, 4.0),
            crs="EPSG:3157",
        )
    with pytest.raises(ValueError, match="cell_size_m"):
        build_change_cells(
            earlier=earlier,
            later=later,
            valid=valid,
            change_bounds=(0.0, 0.0, 4.0, 4.0),
            grid_bounds=(0.0, 0.0, 4.0, 4.0),
            crs="EPSG:3157",
            cell_size_m=0.0,
        )


def test_change_cell_exports(tmp_path: Path) -> None:
    """GeoJSON is WGS84 and PNG/product files are written."""
    earlier, later, valid = _arrays()
    cells = build_change_cells(
        earlier=earlier,
        later=later,
        valid=valid,
        change_bounds=(0.0, 0.0, 4.0, 4.0),
        grid_bounds=(0.0, 0.0, 4.0, 4.0),
        crs="EPSG:3157",
        threshold_m=1.0,
        cell_size_m=4.0,
    )
    collection = change_cells_geojson(cells, crs="EPSG:3157", metadata={"method": "test"})
    features = cast("list[dict[str, object]]", collection["features"])
    geometry = cast("dict[str, object]", features[0]["geometry"])
    coordinates = cast("list[list[list[float]]]", geometry["coordinates"])[0][0]
    assert -180.0 <= coordinates[0] <= 180.0
    assert -90.0 <= coordinates[1] <= 90.0
    assert change_cells_png(cells).startswith(b"\x89PNG")
    paths = write_change_cells(
        cells,
        tmp_path,
        crs="EPSG:3157",
        metadata={"method": "test", "evidence": CHANGE_CELL_EVIDENCE.to_dict()},
    )
    assert paths["json"].exists()
    assert paths["geojson"].exists()
    assert paths["png"].exists()
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == "fresh-urban-forest.canopy-change.v1"
