"""Tests for the Vancouver change-sensitivity script."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from analyze_vancouver_change_sensitivity import _cell_area, run


def _product(path: Path, *, earlier_value: float, later_value: float) -> None:
    """Write a tiny change product directory."""
    path.mkdir()
    earlier = np.full((2, 2), earlier_value, dtype=np.float32)
    later = np.full((2, 2), later_value, dtype=np.float32)
    valid = np.ones((2, 2), dtype=np.bool_)
    np.savez_compressed(path / "change_grid.npz", earlier=earlier, later=later, valid=valid)
    (path / "change.json").write_text(
        json.dumps(
            {
                "bounds": [0.0, 0.0, 4.0, 4.0],
                "valid_overlap_m2": 16.0,
                "metrics": {"net_m2": 0.0},
            }
        ),
        encoding="utf-8",
    )


def test_cell_area_and_run(tmp_path: Path) -> None:
    """The cell area and sensitivity output are deterministic."""
    two = tmp_path / "two"
    five = tmp_path / "five"
    _product(two, earlier_value=2.5, later_value=2.0)
    _product(five, earlier_value=2.5, later_value=2.0)
    assert _cell_area(two / "change.json", (2, 2)) == 4.0
    result = run(
        change_2m=two,
        change_5m=five,
        out_dir=tmp_path / "out",
        threshold_m=2.0,
    )
    assert Path(str(result["path"])).exists()
    summary = result["summary"]
    assert isinstance(summary, dict)
    assert "net_sign_stable" in summary
