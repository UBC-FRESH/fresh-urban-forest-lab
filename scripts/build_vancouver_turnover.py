#!/usr/bin/env python3
"""Build the Vancouver canopy turnover-hotspot product."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

import numpy as np

from fresh_urban_forest.turnover import (
    TURNOVER_EVIDENCE,
    build_turnover_cells,
    write_turnover_product,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Parameters
    ----------
    argv : sequence of str or None
        Arguments. ``None`` uses ``sys.argv``.

    Returns
    -------
    argparse.Namespace
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--change-dir",
        type=Path,
        default=Path("data/processed/change_vancouver_2018_2022_citywide_2m"),
    )
    parser.add_argument(
        "--priority",
        type=Path,
        default=Path("data/processed/vancouver_2022/heat_priority.json"),
    )
    parser.add_argument(
        "--planting",
        type=Path,
        default=Path("data/processed/vancouver_2022/planting_opportunity.json"),
    )
    parser.add_argument(
        "--heat",
        type=Path,
        default=Path("data/processed/vancouver_2022/heat_equity.json"),
    )
    parser.add_argument(
        "--action",
        type=Path,
        default=Path("data/processed/vancouver_2022/canopy_action.json"),
    )
    parser.add_argument("--out", type=Path, default=Path("data/processed/vancouver_2022"))
    parser.add_argument("--min-patch", type=float, default=50.0)
    parser.add_argument("--cell-size", type=float, default=400.0)
    return parser.parse_args(argv)


def _load(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(cell.get("cell_id")): dict(cell) for cell in payload.get("cells", [])}


def _grid_bounds(path: Path, fallback: tuple[float, ...]) -> tuple[float, float, float, float]:
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        metadata = payload.get("metadata", {})
        if isinstance(metadata, Mapping) and "bounds" in metadata:
            values = cast("list[float]", metadata["bounds"])
            return (float(values[0]), float(values[1]), float(values[2]), float(values[3]))
    return (float(fallback[0]), float(fallback[1]), float(fallback[2]), float(fallback[3]))


def build_product(
    *,
    change_dir: Path,
    priority: Path,
    planting: Path,
    heat: Path,
    action: Path,
    out_dir: Path,
    min_patch_m2: float = 50.0,
    cell_size_m: float = 400.0,
) -> dict[str, object]:
    """Build and write the turnover product.

    Parameters
    ----------
    change_dir : Path
        P43 2 m change directory.
    priority : Path
        P38 product.
    planting : Path
        P39 product.
    heat : Path
        P40 product.
    action : Path
        P42 product.
    out_dir : Path
        Output directory.
    min_patch_m2 : float
        Minimum patch area.
    cell_size_m : float
        Global cell size.

    Returns
    -------
    dict
        Cell count, high-tier count, and written paths.
    """
    summary = json.loads((change_dir / "change.json").read_text(encoding="utf-8"))
    grid = np.load(change_dir / "change_grid.npz")
    bounds_raw = cast("list[float]", summary["bounds"])
    change_bounds = (
        float(bounds_raw[0]),
        float(bounds_raw[1]),
        float(bounds_raw[2]),
        float(bounds_raw[3]),
    )
    grid_bounds = _grid_bounds(priority, change_bounds)
    priority_cells = _load(priority)
    cells = build_turnover_cells(
        change=grid["change"],
        valid=grid["valid"],
        change_bounds=change_bounds,
        grid_bounds=grid_bounds,
        crs=str(summary["crs"]),
        min_patch_m2=min_patch_m2,
        cell_size_m=cell_size_m,
        priority=priority_cells,
        planting=_load(planting),
        heat=_load(heat),
        action=_load(action),
    )
    cells = tuple(cell for cell in cells if cell.cell_id in priority_cells)
    metadata: dict[str, object] = {
        "cell_size_m": cell_size_m,
        "min_patch_m2": min_patch_m2,
        "change_resolution_m": 2.0,
        "crs": summary["crs"],
        "methods": {"turnover": TURNOVER_EVIDENCE.to_dict()},
        "caveats": [
            "This is a contiguous gain/loss patch screen, not a net gain or loss claim.",
            "P45 found the citywide net sign unstable across a +/-1 m offset range.",
            "Patch size is sensitive to the 2 m grid, threshold, and vertical offset.",
            "No tree survival, species, ownership, causal, or field-validation claim.",
        ],
    }
    paths = write_turnover_product(
        cells,
        out_dir,
        crs=str(summary["crs"]),
        metadata=metadata,
        stem="canopy_turnover",
    )
    meta_path = out_dir / "canopy_turnover_meta.json"
    meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return {
        "cell_count": len(cells),
        "high_tier_cells": sum(1 for cell in cells if cell.turnover_tier == "high"),
        "paths": {name: str(path) for name, path in paths.items()} | {"metadata": str(meta_path)},
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run the turnover build.

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
    result = build_product(
        change_dir=args.change_dir,
        priority=args.priority,
        planting=args.planting,
        heat=args.heat,
        action=args.action,
        out_dir=args.out,
        min_patch_m2=args.min_patch,
        cell_size_m=args.cell_size,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
