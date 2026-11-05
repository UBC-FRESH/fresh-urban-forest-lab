#!/usr/bin/env python3
"""Build the full Vancouver inventory pack from the public-tree CSV and city CHM."""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path
from typing import cast

from fresh_urban_forest.city_inventory import (
    enrich_city_inventory,
    inventory_summary,
    load_city_inventory,
)
from fresh_urban_forest.models import tree_to_dict


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
        "--csv",
        type=Path,
        default=Path("data/raw/vancouver/public_trees.csv"),
        help="City public-tree CSV",
    )
    parser.add_argument(
        "--dem",
        type=Path,
        default=Path("data/processed/vancouver_2022/dem.tif"),
        help="City DEM",
    )
    parser.add_argument(
        "--chm",
        type=Path,
        default=Path("data/processed/vancouver_2022/chm.tif"),
        help="City CHM",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/processed/vancouver_2022"),
        help="Output directory",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the inventory build.

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
    if not args.dem.exists() or not args.chm.exists():
        print("city DEM/CHM not found; run scripts/build_vancouver_city.py first", file=sys.stderr)
        return 1
    inventory = load_city_inventory(args.csv)
    print(f"loaded {len(inventory.trees)} of {inventory.source_rows} source rows")
    inventory = enrich_city_inventory(inventory, dem_path=args.dem, chm_path=args.chm)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    tree_path = args.out_dir / "trees.json.gz"
    with gzip.open(tree_path, "wt", encoding="utf-8") as handle:
        json.dump([tree_to_dict(tree) for tree in inventory.trees], handle)
    summary = inventory_summary(inventory)
    (args.out_dir / "inventory_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    comparison = summary["height_comparison"]
    overall = cast(dict[str, object], comparison)["overall"]
    stats = cast(dict[str, float | int], overall)
    print(
        f"mapped {summary['mapped_rows']} trees; "
        f"height pairs {stats['n']}; "
        f"bias {stats['bias_m']} m"
    )
    print(f"wrote {tree_path} and {args.out_dir / 'inventory_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
