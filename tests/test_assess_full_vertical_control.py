"""Tests for full-city vertical-control assessment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from assess_full_vertical_control import assess

BOUNDS = (-123.20, 49.20, -123.10, 49.30)


def _write_tile(path: Path, size: int) -> None:
    """Write a dummy tile with a fixed size."""
    path.write_bytes(b"x" * size)


def test_assess_passes_complete_stable_sample(tmp_path: Path) -> None:
    """Complete, centred tiles produce a passing gate."""
    tiles = tmp_path / "tiles"
    tiles.mkdir()
    index_tiles = []
    control_tiles = []
    for index in range(4):
        filename = f"tile{index}.zip"
        _write_tile(tiles / filename, 10)
        lon = BOUNDS[0] + 0.02 + index * 0.02
        lat = BOUNDS[1] + 0.02 + index * 0.02
        index_tiles.append(
            {
                "tile_id": f"tile{index}",
                "filename": filename,
                "size_bytes": 10,
                "bbox": [lon - 0.005, lat - 0.005, lon + 0.005, lat + 0.005],
            }
        )
        control_tiles.append({"tile": filename, "median_m": 0.01, "count": 100})
    index_path = tmp_path / "index.json"
    index_path.write_text(json.dumps({"tiles": index_tiles}), encoding="utf-8")
    control = tmp_path / "control.json"
    control.write_text(
        json.dumps({"estimate": {"offset_m": 0.01}, "tiles": control_tiles}), encoding="utf-8"
    )
    out = tmp_path / "assessment.json"
    payload = assess(
        argparse.Namespace(
            index=index_path,
            tiles=tiles,
            control=control,
            out=out,
            tolerance_m=0.15,
            max_trend_m=0.10,
            outlier_m=0.20,
        )
    )
    assert payload["gate_passed"] is True
    assert payload["complete_tile_count"] == 4
    assert payload["within_tolerance_count"] == 4
    assert out.exists()


def test_assess_reports_missing_tiles(tmp_path: Path) -> None:
    """Missing required tiles fail the coverage gate."""
    tiles = tmp_path / "tiles"
    tiles.mkdir()
    index = tmp_path / "index.json"
    index.write_text(
        json.dumps(
            {
                "tiles": [
                    {
                        "tile_id": "missing",
                        "filename": "missing.zip",
                        "size_bytes": 10,
                        "bbox": [-123.2, 49.2, -123.19, 49.21],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    control = tmp_path / "control.json"
    control.write_text(
        json.dumps({"tiles": [{"tile": "missing.zip", "median_m": 0.0, "count": 1}]}),
        encoding="utf-8",
    )
    payload = assess(
        argparse.Namespace(
            index=index,
            tiles=tiles,
            control=control,
            out=tmp_path / "assessment.json",
            tolerance_m=0.15,
            max_trend_m=0.10,
            outlier_m=0.20,
        )
    )
    assert payload["gate_passed"] is False
    assert payload["missing_tiles"] == ["missing"]
