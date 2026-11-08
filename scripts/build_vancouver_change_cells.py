#!/usr/bin/env python3
"""Build 400 m observed-change cells and join P38-P40 screens."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

import numpy as np

from fresh_urban_forest.change_cells import (
    CHANGE_CELL_EVIDENCE,
    CHANGE_JOIN_EVIDENCE,
    build_change_cells,
    write_change_cells,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Parameters
    ----------
    argv : sequence of str or None
        Arguments.

    Returns
    -------
    argparse.Namespace
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--change-dir",
        type=Path,
        default=Path("data/processed/change_vancouver_2018_2022_downtown"),
        help="Directory with change.json and change_grid.npz",
    )
    parser.add_argument(
        "--heat-priority",
        type=Path,
        default=Path("data/processed/vancouver_2022/heat_priority.json"),
    )
    parser.add_argument(
        "--planting",
        type=Path,
        default=Path("data/processed/vancouver_2022/planting_opportunity.json"),
    )
    parser.add_argument(
        "--heat-equity",
        type=Path,
        default=Path("data/processed/vancouver_2022/heat_equity.json"),
    )
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--threshold", type=float, default=2.0)
    parser.add_argument("--cell-size", type=float, default=400.0)
    return parser.parse_args(argv)


def load_cells(path: Path) -> dict[str, dict[str, object]]:
    """Load a P38/P39/P40 product as a cell lookup.

    Parameters
    ----------
    path : Path
        Product JSON.

    Returns
    -------
    dict
        Cell id to properties. Missing files return an empty mapping.
    """
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(cell.get("cell_id")): dict(cell) for cell in payload.get("cells", [])}


def build_product(
    *,
    change_dir: Path,
    heat_priority: Path,
    planting: Path,
    heat_equity: Path,
    out_dir: Path,
    threshold_m: float = 2.0,
    cell_size_m: float = 400.0,
) -> dict[str, object]:
    """Build and write the change-cell product.

    Parameters
    ----------
    change_dir : Path
        Directory with the 1 m change product.
    heat_priority : Path
        P38 cells.
    planting : Path
        P39 cells.
    heat_equity : Path
        P40 cells.
    out_dir : Path
        Output directory.
    threshold_m : float
        Canopy threshold.
    cell_size_m : float
        Global cell size.

    Returns
    -------
    dict
        Summary and written paths.
    """
    summary = json.loads((change_dir / "change.json").read_text(encoding="utf-8"))
    grid = np.load(change_dir / "change_grid.npz")
    priority = load_cells(heat_priority)
    planting_cells = load_cells(planting)
    heat_cells = load_cells(heat_equity)
    p38_payload = (
        json.loads(heat_priority.read_text(encoding="utf-8")) if heat_priority.exists() else {}
    )
    p38_metadata = p38_payload.get("metadata", {}) if isinstance(p38_payload, Mapping) else {}
    grid_bounds = tuple(
        float(value) for value in cast("list[float]", p38_metadata.get("bounds", summary["bounds"]))
    )
    change_bounds_raw = cast("list[float]", summary["bounds"])
    change_bounds = (
        float(change_bounds_raw[0]),
        float(change_bounds_raw[1]),
        float(change_bounds_raw[2]),
        float(change_bounds_raw[3]),
    )
    cells = build_change_cells(
        earlier=grid["earlier"],
        later=grid["later"],
        valid=grid["valid"],
        change_bounds=change_bounds,
        grid_bounds=(grid_bounds[0], grid_bounds[1], grid_bounds[2], grid_bounds[3]),
        crs=str(summary["crs"]),
        threshold_m=threshold_m,
        cell_size_m=cell_size_m,
        priority=priority,
        planting=planting_cells,
        heat=heat_cells,
    )
    metadata: dict[str, object] = {
        "earlier_label": summary.get("earlier_label"),
        "later_label": summary.get("later_label"),
        "threshold_m": threshold_m,
        "cell_size_m": cell_size_m,
        "change_bounds": summary.get("bounds"),
        "crs": summary.get("crs"),
        "overlap_m2": summary.get("valid_overlap_m2"),
        "methods": {
            "change": CHANGE_CELL_EVIDENCE.to_dict(),
            "joins": CHANGE_JOIN_EVIDENCE.to_dict(),
        },
        "caveats": [
            "This is a thresholded LiDAR surface comparison, not tree survival or growth.",
            "2018 and 2022 differ in acquisition date, point density, and possible "
            "co-registration error.",
            "Joins to shade, gap, and heat scores are descriptive, not causal.",
            "The approved pilot AOI is two downtown tiles; this is not a city-wide change claim.",
        ],
    }
    paths = write_change_cells(
        cells,
        out_dir,
        crs=str(summary["crs"]),
        metadata=metadata,
        stem="canopy_change",
    )
    meta_path = out_dir / "canopy_change_meta.json"
    meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return {
        "cell_count": len(cells),
        "change_metrics": summary.get("metrics"),
        "paths": {name: str(path) for name, path in paths.items()} | {"metadata": str(meta_path)},
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run the change-cell build.

    Parameters
    ----------
    argv : sequence of str or None
        Arguments.

    Returns
    -------
    int
        Zero on success.
    """
    args = parse_args(argv)
    out_dir = args.out or args.change_dir
    result = build_product(
        change_dir=args.change_dir,
        heat_priority=args.heat_priority,
        planting=args.planting,
        heat_equity=args.heat_equity,
        out_dir=out_dir,
        threshold_m=args.threshold,
        cell_size_m=args.cell_size,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
