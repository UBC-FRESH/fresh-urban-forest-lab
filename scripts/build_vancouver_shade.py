#!/usr/bin/env python3
"""Compute representative-day city shade and merge it into city_metrics.json."""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
from dataclasses import replace
from pathlib import Path
from zoneinfo import ZoneInfo

from fresh_urban_forest.dataset import load_dataset
from fresh_urban_forest.models import tree_from_dict
from fresh_urban_forest.shade import shade_period


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
        "--root",
        type=Path,
        default=Path("data/processed/vancouver_2022"),
        help="City dataset directory",
    )
    parser.add_argument("--year", type=int, default=2022)
    parser.add_argument("--target-height", type=float, default=1.5)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the shade calculation.

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
    root = args.root
    dataset = load_dataset(root)
    with gzip.open(root / "trees.json.gz", "rt", encoding="utf-8") as handle:
        full_trees = tuple(tree_from_dict(item) for item in json.load(handle))
    dataset = replace(dataset, trees=full_trees)
    zone = ZoneInfo("America/Vancouver")
    whens = tuple(
        dt.datetime(args.year, month, day, hour, tzinfo=zone)
        for month, day in ((6, 21), (9, 21))
        for hour in (10, 12, 14, 16)
    )
    period = shade_period(
        dataset,
        whens,
        target_height_m=args.target_height,
        step_hours=2.0,
        include_terrain=False,
    )
    shade = {
        "whens": [when.isoformat() for when in whens],
        "target_height_m": args.target_height,
        "tree_count": len(full_trees),
        "metrics": period.metrics,
        "method": "projected 2.5-D crown and building silhouettes; 2-hour samples",
        "tier": "screening",
        "limits": "No penumbra, leaf transmissivity, or terrain horizon; representative days only.",
    }
    metrics_path = root / "city_metrics.json"
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    payload["shade"] = shade
    metrics_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (root / "shade_city.json").write_text(json.dumps(shade, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(shade["metrics"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
