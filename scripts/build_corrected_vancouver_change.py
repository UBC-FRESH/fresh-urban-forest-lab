#!/usr/bin/env python3
"""Build a versioned P43 change product corrected by measured ground control.

The source P43 product remains untouched. The correction is applied to the earlier
canopy-height grid, using the measured 2018-ground minus 2022-DEM offset and the +1.0 m
offset already assumed by P43.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from fresh_urban_forest.change_product import build_change_product
from fresh_urban_forest.models import TerrainGrid


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Parameters
    ----------
    argv : list of str or None
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
        default=Path(
            "/srv/shared-data/gep/ws4/p43-worktree/data/processed/change_vancouver_2018_2022_citywide_2m"
        ),
    )
    parser.add_argument(
        "--control",
        type=Path,
        default=Path("data/processed/vertical_control_sample34.json"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/processed/change_vancouver_2018_2022_citywide_2m_control"),
    )
    parser.add_argument("--p43-offset", type=float, default=1.0)
    parser.add_argument(
        "--earlier-label",
        default="City of Vancouver LiDAR 2018 (ground-control corrected)",
        help="Label for the corrected earlier surface",
    )
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> dict[str, object]:
    """Build the corrected product and write control metadata.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments.

    Returns
    -------
    dict
        Corrected metrics, correction, and output path.
    """
    control = json.loads(args.control.read_text(encoding="utf-8"))
    estimate = control["estimate"]
    offset = float(estimate["offset_m"])
    low = float(estimate["bootstrap_low_m"])
    high = float(estimate["bootstrap_high_m"])
    correction = args.p43_offset - offset
    correction_low = args.p43_offset - high
    correction_high = args.p43_offset - low
    summary = json.loads((args.change_dir / "change.json").read_text(encoding="utf-8"))
    grid = np.load(args.change_dir / "change_grid.npz")
    earlier = np.asarray(grid["earlier"], dtype=np.float64)
    later = np.asarray(grid["later"], dtype=np.float64)
    valid = np.asarray(grid["valid"], dtype=np.bool_)
    elevation = np.asarray(grid["elevation"], dtype=np.float32)
    corrected = np.where(valid, earlier + correction, np.nan)
    target = np.where(valid, later, np.nan)
    bounds_values = summary["bounds"]
    bounds: tuple[float, float, float, float] = (
        float(bounds_values[0]),
        float(bounds_values[1]),
        float(bounds_values[2]),
        float(bounds_values[3]),
    )
    earlier_grid = TerrainGrid(
        crs=str(summary["crs"]),
        bounds=bounds,
        width=corrected.shape[1],
        height=corrected.shape[0],
        elevation=elevation,
        canopy_height=corrected.astype(np.float32),
    )
    later_grid = TerrainGrid(
        crs=str(summary["crs"]),
        bounds=bounds,
        width=target.shape[1],
        height=target.shape[0],
        elevation=elevation,
        canopy_height=target.astype(np.float32),
    )
    args.out.mkdir(parents=True, exist_ok=True)
    build_change_product(
        earlier_grid,
        later_grid,
        args.out,
        threshold_m=2.0,
        earlier_label=args.earlier_label,
        later_label="City of Vancouver LiDAR 2022 (citywide)",
    )
    change_path = args.out / "change.json"
    payload = json.loads(change_path.read_text(encoding="utf-8"))
    payload["control"] = {
        "control_offset_m": offset,
        "control_interval_m": [low, high],
        "p43_assumed_offset_m": args.p43_offset,
        "correction_to_earlier_m": correction,
        "correction_interval_m": [correction_low, correction_high],
        "control_surface": estimate["surface"],
        "control_count": estimate["count"],
        "source_product": str(args.change_dir),
        "status": "corrected screen; not a final citywide direction",
        "caveats": control.get("caveats", []),
    }
    change_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    metadata = {
        "source_product": str(args.change_dir),
        "control_estimate": estimate,
        "p43_assumed_offset_m": args.p43_offset,
        "correction_to_earlier_m": correction,
        "correction_interval_m": [correction_low, correction_high],
        "output": str(args.out),
    }
    (args.out / "control_metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "metrics": payload["metrics"],
        "correction_m": correction,
        "correction_interval_m": [correction_low, correction_high],
        "out": str(args.out),
    }


def main(argv: list[str] | None = None) -> int:
    """Run the corrected product build.

    Parameters
    ----------
    argv : list of str or None
        Command-line arguments.

    Returns
    -------
    int
        Zero on success.
    """
    args = parse_args(argv)
    print(json.dumps(run(args), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
