#!/usr/bin/env python3
"""Assess full-city vertical-control coverage, spatial stability, and gate status."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np


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
        "--index",
        type=Path,
        default=Path(
            "/srv/shared-data/gep/ws4/p43-worktree/data/raw/tiles/vancouver_2018_city.json"
        ),
    )
    parser.add_argument("--tiles", type=Path, default=Path("data/raw/tiles"))
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--tolerance-m", type=float, default=0.15)
    parser.add_argument("--max-trend-m", type=float, default=0.10)
    parser.add_argument(
        "--outlier-m",
        type=float,
        default=0.20,
        help="Exclude tiles farther than this from the sample median for stability checks",
    )
    return parser.parse_args(argv)


def _weighted_trend(
    x: np.ndarray, y: np.ndarray, z: np.ndarray, w: np.ndarray
) -> tuple[float, float]:
    """Return the weighted easting and northing range from a planar fit."""
    design = np.column_stack([np.ones(len(x)), x - x.mean(), y - y.mean()])
    weights = np.sqrt(w)
    coefficients = np.linalg.lstsq(design * weights[:, None], z * weights, rcond=None)[0]
    return (
        float(coefficients[1] * (x.max() - x.min())),
        float(coefficients[2] * (y.max() - y.min())),
    )


def assess(args: argparse.Namespace) -> dict[str, object]:
    """Assess coverage and spatial control stability.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments.

    Returns
    -------
    dict
        Coverage, spatial summary, and gate decision.
    """
    index = json.loads(args.index.read_text(encoding="utf-8"))["tiles"]
    by_filename = {str(tile["filename"]): tile for tile in index}
    missing = []
    complete = 0
    for tile in index:
        path = args.tiles / str(tile["filename"])
        if path.exists() and path.stat().st_size == int(tile["size_bytes"]):
            complete += 1
        else:
            missing.append(str(tile["tile_id"]))
    control = json.loads(args.control.read_text(encoding="utf-8"))
    rows = []
    for row in control.get("tiles", []):
        tile = by_filename.get(str(row["tile"]))
        if tile is None:
            continue
        bbox = [float(value) for value in tile["bbox"]]
        lon = (bbox[0] + bbox[2]) / 2.0
        lat = (bbox[1] + bbox[3]) / 2.0
        rows.append(
            (
                (lon - 0.0) * 111_320.0 * math.cos(math.radians(lat)),
                lat * 110_540.0,
                float(row["median_m"]),
                float(row["count"]),
                str(row["tile"]),
            )
        )
    if not rows:
        raise ValueError("no control tiles matched the index")
    x = np.array([row[0] for row in rows])
    y = np.array([row[1] for row in rows])
    z = np.array([row[2] for row in rows])
    w = np.array([row[3] for row in rows])
    median = float(np.median(z))
    keep = np.abs(z - median) <= args.outlier_m
    x_in = x[keep]
    y_in = y[keep]
    z_in = z[keep]
    w_in = w[keep]
    within = int(np.count_nonzero(np.abs(z_in - median) <= args.tolerance_m))
    easting_range, northing_range = _weighted_trend(x_in, y_in, z_in, w_in)
    gate = (
        complete == len(index)
        and within / len(z_in) >= 0.90
        and abs(easting_range) <= args.max_trend_m
        and abs(northing_range) <= args.max_trend_m
    )
    payload = {
        "schema_version": "fresh-urban-forest.full-control-assessment.v1",
        "index_tile_count": len(index),
        "complete_tile_count": complete,
        "missing_tiles": missing,
        "control_tile_count": len(rows),
        "control_estimate": control.get("estimate"),
        "tile_median_min_m": round(float(z.min()), 4),
        "tile_median_max_m": round(float(z.max()), 4),
        "tile_median_median_m": round(median, 4),
        "outlier_threshold_m": args.outlier_m,
        "outlier_tiles": [row[4] for row in rows if abs(row[2] - median) > args.outlier_m],
        "stability_tile_count": len(z_in),
        "within_tolerance_count": within,
        "within_tolerance_fraction": round(within / len(z_in), 4),
        "tolerance_m": args.tolerance_m,
        "easting_trend_m": round(easting_range, 4),
        "northing_trend_m": round(northing_range, 4),
        "max_trend_m": args.max_trend_m,
        "gate_passed": gate,
        "decision": (
            "Proceed to corrected-product publication."
            if gate
            else "Stop at the full control report; do not publish a corrected direction."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    """Run the full control assessment.

    Parameters
    ----------
    argv : list of str or None
        Command-line arguments.

    Returns
    -------
    int
        Zero on success.
    """
    print(json.dumps(assess(parse_args(argv)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
