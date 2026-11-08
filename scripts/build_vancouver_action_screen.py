#!/usr/bin/env python3
"""Build the integrated Vancouver canopy-action screening product."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from fresh_urban_forest.action_screen import (
    ACTION_EVIDENCE,
    build_action_cells,
    write_action_product,
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
        "--change",
        type=Path,
        default=Path("data/processed/change_vancouver_2018_2022_citywide/canopy_change.json"),
    )
    parser.add_argument("--out", type=Path, default=Path("data/processed/vancouver_2022"))
    return parser.parse_args(argv)


def load_cells(path: Path) -> dict[str, dict[str, object]]:
    """Load a product as a cell-id lookup.

    Parameters
    ----------
    path : Path
        Product JSON.

    Returns
    -------
    dict
        Cell id to properties.

    Raises
    ------
    FileNotFoundError
        When the product is missing.
    """
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(cell.get("cell_id")): dict(cell) for cell in payload.get("cells", [])}


def _metadata(path: Path) -> Mapping[str, object]:
    """Return a product's metadata mapping."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    metadata = payload.get("metadata", {})
    return metadata if isinstance(metadata, Mapping) else {}


def build_product(
    *,
    priority_path: Path,
    planting_path: Path,
    heat_path: Path,
    change_path: Path,
    out_dir: Path,
) -> dict[str, object]:
    """Build and write the action product.

    Parameters
    ----------
    priority_path : Path
        P38 product.
    planting_path : Path
        P39 product.
    heat_path : Path
        P40 product.
    change_path : Path
        P41 product.
    out_dir : Path
        Output directory.

    Returns
    -------
    dict
        Summary and paths.
    """
    priority = load_cells(priority_path)
    planting = load_cells(planting_path)
    heat = load_cells(heat_path)
    change = load_cells(change_path)
    crs = str(_metadata(priority_path).get("crs", "EPSG:3157"))
    cells = build_action_cells(
        priority=priority,
        planting=planting,
        heat=heat,
        change=change,
        crs=crs,
    )
    counts: dict[str, int] = {}
    for cell in cells:
        counts[cell.action_class] = counts.get(cell.action_class, 0) + 1
    metadata: dict[str, object] = {
        "cell_size_m": 400.0,
        "crs": crs,
        "cell_count": len(cells),
        "change_observed_cells": sum(1 for cell in cells if cell.change_observed),
        "action_counts": counts,
        "methods": {"action": ACTION_EVIDENCE.to_dict()},
        "caveats": [
            "This is a screening action label, not a planting plan.",
            "Costs, utilities, ownership, access, soil, irrigation, and field validation "
            "are not modelled.",
            "P43 change is a citywide 5 m thresholded LiDAR surface comparison; "
            "it is not tree survival or growth.",
            "The joins are descriptive and do not establish cause.",
        ],
    }
    paths = write_action_product(
        cells,
        out_dir,
        crs=crs,
        metadata=metadata,
        stem="canopy_action",
    )
    meta_path = out_dir / "canopy_action_meta.json"
    meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return {
        "cell_count": len(cells),
        "action_counts": counts,
        "paths": {name: str(path) for name, path in paths.items()} | {"metadata": str(meta_path)},
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run the action-screen build.

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
        priority_path=args.priority,
        planting_path=args.planting,
        heat_path=args.heat,
        change_path=args.change,
        out_dir=args.out,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
