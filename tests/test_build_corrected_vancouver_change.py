"""Tests for the P51 corrected change-product build."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from build_corrected_vancouver_change import run

BOUNDS = (0.0, 0.0, 40.0, 40.0)


def test_run_writes_corrected_product_and_control_metadata(tmp_path: Path) -> None:
    """A small corrected product preserves the control correction and output."""
    change_dir = tmp_path / "change"
    change_dir.mkdir()
    shape = (20, 20)
    earlier = np.full(shape, np.nan, dtype=np.float64)
    later = np.full(shape, np.nan, dtype=np.float64)
    valid = np.ones(shape, dtype=np.bool_)
    earlier[2:8, 2:8] = 3.0
    later[2:8, 2:8] = 3.0
    earlier[10:15, 10:15] = 1.0
    later[10:15, 10:15] = 3.0
    np.savez_compressed(
        change_dir / "change_grid.npz",
        earlier=earlier,
        later=later,
        valid=valid,
        elevation=np.zeros(shape, dtype=np.float32),
    )
    (change_dir / "change.json").write_text(
        json.dumps({"bounds": list(BOUNDS), "crs": "EPSG:3157"}), encoding="utf-8"
    )
    control = tmp_path / "control.json"
    control.write_text(
        json.dumps(
            {
                "estimate": {
                    "surface": "test",
                    "offset_m": 0.5,
                    "bootstrap_low_m": 0.4,
                    "bootstrap_high_m": 0.6,
                    "count": 10,
                },
                "caveats": ["test caveat"],
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "corrected"
    result = run(
        argparse.Namespace(
            change_dir=change_dir,
            control=control,
            out=out,
            p43_offset=1.0,
            earlier_label="test corrected",
        )
    )
    assert result["correction_m"] == 0.5
    assert (out / "change.json").exists()
    assert (out / "change_grid.npz").exists()
    metadata = json.loads((out / "control_metadata.json").read_text(encoding="utf-8"))
    assert metadata["correction_to_earlier_m"] == 0.5
    payload = json.loads((out / "change.json").read_text(encoding="utf-8"))
    assert payload["control"]["correction_to_earlier_m"] == 0.5
