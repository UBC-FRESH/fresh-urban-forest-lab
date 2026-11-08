#!/usr/bin/env python3
"""Analyze the P43 citywide change screen's offset and scale sensitivity."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from fresh_urban_forest.change_sensitivity import (
    offset_sensitivity,
    summarize_sensitivity,
    write_sensitivity,
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
        "--change-2m",
        type=Path,
        default=Path("data/processed/change_vancouver_2018_2022_citywide_2m"),
    )
    parser.add_argument(
        "--change-5m",
        type=Path,
        default=Path("data/processed/change_vancouver_2018_2022_citywide"),
    )
    parser.add_argument("--out", type=Path, default=Path("data/processed/vancouver_2022"))
    parser.add_argument("--threshold", type=float, default=2.0)
    return parser.parse_args(argv)


def _cell_area(change_json: Path, shape: tuple[int, int]) -> float:
    """Return cell area from a change summary."""
    payload = json.loads(change_json.read_text(encoding="utf-8"))
    left, bottom, right, top = (float(value) for value in payload["bounds"])
    return (right - left) * (top - bottom) / (shape[0] * shape[1])


def run(
    *,
    change_2m: Path,
    change_5m: Path,
    out_dir: Path,
    threshold_m: float = 2.0,
) -> dict[str, object]:
    """Run the citywide sensitivity analysis.

    Parameters
    ----------
    change_2m : Path
        P43 2 m change directory.
    change_5m : Path
        Rejected 5 m change directory.
    out_dir : Path
        Output directory.
    threshold_m : float
        Canopy threshold.

    Returns
    -------
    dict
        Summary and output path.
    """
    grid = np.load(change_2m / "change_grid.npz")
    earlier = grid["earlier"]
    later = grid["later"]
    valid = grid["valid"]
    area = _cell_area(change_2m / "change.json", earlier.shape)
    results = offset_sensitivity(
        earlier,
        later,
        valid,
        offsets_m=(-1.0, -0.5, 0.0, 0.5, 1.0),
        threshold_m=threshold_m,
        cell_area_m2=area,
    )
    summary = summarize_sensitivity(results)
    five = json.loads((change_5m / "change.json").read_text(encoding="utf-8"))
    two = json.loads((change_2m / "change.json").read_text(encoding="utf-8"))
    summary["scale_2m"] = two["metrics"]
    summary["scale_5m_rejected"] = five["metrics"]
    summary["five_m_valid_overlap_m2"] = five["valid_overlap_m2"]
    summary["claim_rule"] = (
        "If net signs differ across the offset range, do not claim a direction; report the range."
    )
    path = write_sensitivity(results, summary, out_dir)
    return {"summary": summary, "path": str(path)}


def main(argv: Sequence[str] | None = None) -> int:
    """Run the sensitivity analysis.

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
    result = run(
        change_2m=args.change_2m,
        change_5m=args.change_5m,
        out_dir=args.out,
        threshold_m=args.threshold,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
