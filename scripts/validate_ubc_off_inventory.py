#!/usr/bin/env python3
"""Run the frozen City detector against the independent UBC inventory and CHM."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
import rasterio

from fresh_urban_forest.city_off_inventory import detect_city_trees
from fresh_urban_forest.ubc_validation import (
    attribute_errors,
    one_to_one_matches,
    ubc_tree_records,
)


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
        "--chm",
        type=Path,
        default=Path("data/raw/ubc/lidar_2021/CHM_1m.tif"),
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path("data/raw/vancouver/ubc_campus_trees.geojson"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/vancouver_2022/off_inventory_ubc_validation.json"),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the independent UBC validation.

    Parameters
    ----------
    argv : list of str or None
        Command-line arguments. ``None`` uses ``sys.argv``.

    Returns
    -------
    int
        Process status.
    """
    args = parse_args(argv)
    detected = detect_city_trees(args.chm)
    trees = ubc_tree_records(gpd.read_file(args.inventory))
    with rasterio.open(args.chm) as dataset:
        left, bottom, right, top = dataset.bounds
    trees = tuple(
        tree
        for tree in trees
        if tree.x_m is not None
        and tree.y_m is not None
        and left <= tree.x_m < right
        and bottom <= tree.y_m < top
    )
    mapping, summary = one_to_one_matches(detected, trees)
    errors = attribute_errors(mapping, detected, trees)
    payload = {
        "schema_version": "fresh-urban-forest.off-inventory.ubc-validation.v1",
        "status": "independent detection/attribute test; UBC inventory is incomplete",
        "chm": str(args.chm),
        "detector": (
            "frozen City 2 m block-max CHM, 1 km tiles, 40 m buffer, 5 m window, "
            "3 m minimum height, watershed centroids"
        ),
        "detected_count": len(detected),
        "summary": {
            "eligible": summary.eligible,
            "matched": summary.matched,
            "recall": summary.recall,
            "missed_nearest_distance_p50_m": summary.missed_nearest_distance_p50_m,
            "missed_nearest_distance_p95_m": summary.missed_nearest_distance_p95_m,
        },
        "attribute_errors": errors,
        "caveats": [
            "UBC inventory is incomplete and contains location-only records.",
            "One-to-one matching at 5 m is a screening rule, not field validation.",
            "DBH errors use the City unknown-species height-DBH allometry.",
            "No parameter tuning was performed on UBC.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    print(json.dumps(payload["attribute_errors"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
