#!/usr/bin/env python3
"""Compute Vancouver city and local-area canopy and ecosystem-service metrics."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from fresh_urban_forest.city_metrics import compute_city_metrics
from fresh_urban_forest.models import tree_from_dict


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
        "--trees",
        type=Path,
        default=Path("data/processed/vancouver_2022/trees.json.gz"),
        help="Enriched tree inventory",
    )
    parser.add_argument(
        "--chm",
        type=Path,
        default=Path("data/processed/vancouver_2022/chm.tif"),
        help="City CHM",
    )
    parser.add_argument(
        "--building-mask",
        type=Path,
        default=Path("data/processed/vancouver_2022/building_mask.tif"),
        help="Building mask",
    )
    parser.add_argument(
        "--water-mask",
        type=Path,
        default=Path("data/processed/vancouver_2022/water_mask.tif"),
        help="Water mask",
    )
    parser.add_argument(
        "--aoi",
        type=Path,
        default=Path("data/raw/vancouver/local_area_boundary.geojson"),
        help="Local-area polygons",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/processed/vancouver_2022"),
        help="Output directory",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the metrics build.

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
    with gzip.open(args.trees, "rt", encoding="utf-8") as handle:
        trees = tuple(tree_from_dict(item) for item in json.load(handle))
    payload = compute_city_metrics(
        trees,
        chm_path=args.chm,
        building_mask_path=args.building_mask,
        water_mask_path=args.water_mask,
        aoi_path=args.aoi,
        out_dir=args.out_dir,
    )
    city = payload["city"]
    print(json.dumps(city, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
