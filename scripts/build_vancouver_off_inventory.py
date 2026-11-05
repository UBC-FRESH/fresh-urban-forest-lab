#!/usr/bin/env python3
"""Build the full-city ALS off-inventory candidate layer."""

from __future__ import annotations

import argparse
import gzip
import json
import time
from pathlib import Path

import numpy as np

from fresh_urban_forest.city_off_inventory import (
    build_city_candidates,
    classify_land_context,
    detect_city_trees,
    match_inventory,
    write_city_candidates,
)
from fresh_urban_forest.itd import DetectedTree
from fresh_urban_forest.models import TreeRecord, tree_from_dict


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
    parser.add_argument("--root", type=Path, default=Path("data/processed/vancouver_2022"))
    parser.add_argument(
        "--trees",
        type=Path,
        default=Path("data/processed/vancouver_2022/trees.json.gz"),
    )
    parser.add_argument("--chm", type=Path, default=Path("data/processed/vancouver_2022/chm.tif"))
    parser.add_argument(
        "--parcels",
        type=Path,
        default=Path("data/raw/vancouver/property-parcel-polygons.geojson"),
    )
    parser.add_argument(
        "--parks",
        type=Path,
        default=Path("data/raw/vancouver/parks-polygon-representation.geojson"),
    )
    parser.add_argument(
        "--roads",
        type=Path,
        default=Path("data/processed/vancouver_2022/roads.geojson.gz"),
    )
    parser.add_argument(
        "--zoning",
        type=Path,
        default=Path("data/raw/vancouver/zoning-districts-and-labels.geojson"),
    )
    parser.add_argument(
        "--building-mask",
        type=Path,
        default=Path("data/processed/vancouver_2022/building_mask.tif"),
    )
    parser.add_argument(
        "--water-mask",
        type=Path,
        default=Path("data/processed/vancouver_2022/water_mask.tif"),
    )
    parser.add_argument(
        "--detected-cache",
        type=Path,
        default=Path("data/processed/vancouver_2022/detected_city.json.gz"),
    )
    parser.add_argument("--reuse-detected", action="store_true")
    return parser.parse_args(argv)


def load_trees(path: Path) -> tuple[TreeRecord, ...]:
    """Load the full enriched tree inventory.

    Parameters
    ----------
    path : Path
        Compressed JSON tree inventory.

    Returns
    -------
    tuple of TreeRecord
        Public tree records.
    """
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return tuple(tree_from_dict(item) for item in json.load(handle))


def load_detected(path: Path) -> tuple[DetectedTree, ...]:
    """Load cached detected crowns.

    Parameters
    ----------
    path : Path
        Compressed JSON detection cache.

    Returns
    -------
    tuple of DetectedTree
        Cached detected crowns.
    """
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    return tuple(DetectedTree(**item) for item in payload)


def save_detected(trees: tuple[DetectedTree, ...], path: Path) -> None:
    """Save detected crowns as compressed JSON.

    Parameters
    ----------
    trees : tuple of DetectedTree
        Detected crowns.
    path : Path
        Destination compressed JSON path.
    """
    from dataclasses import asdict

    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump([asdict(tree) for tree in trees], handle, separators=(",", ":"))


def main(argv: list[str] | None = None) -> int:
    """Run the city off-inventory build.

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
    started = time.perf_counter()
    if args.reuse_detected and args.detected_cache.exists():
        detected = load_detected(args.detected_cache)
        print(f"loaded {len(detected)} detected crowns from cache", flush=True)
    else:
        detected = detect_city_trees(args.chm)
        print(
            f"detected {len(detected)} crowns in {time.perf_counter() - started:.1f}s",
            flush=True,
        )
        save_detected(detected, args.detected_cache)
    trees = load_trees(args.trees)
    match = match_inventory(detected, trees)
    print(
        f"matched {match.matched} public trees; unmatched {len(match.unmatched_detected)}",
        flush=True,
    )
    xs = np.asarray([tree.x for tree in detected], dtype=np.float64)
    ys = np.asarray([tree.y for tree in detected], dtype=np.float64)
    roads_path = args.roads
    if roads_path.suffix == ".gz":
        with gzip.open(roads_path, "rt", encoding="utf-8") as source:
            payload = json.load(source)
        roads_path = args.root / "roads.tmp.geojson"
        roads_path.write_text(json.dumps(payload), encoding="utf-8")
    land_classes = classify_land_context(
        xs,
        ys,
        parcels_path=args.parcels,
        parks_path=args.parks,
        roads_path=roads_path,
        zoning_path=args.zoning,
    )
    candidates = build_city_candidates(
        detected,
        match,
        trees,
        land_classes,
        building_mask_path=args.building_mask,
        water_mask_path=args.water_mask,
    )
    summary = write_city_candidates(
        candidates,
        dataset_id="vancouver-city-2022",
        detected_count=len(detected),
        matched_count=match.matched,
        unmatched_inventory_count=len(match.unmatched_inventory),
        out_dir=args.root,
    )
    print(summary.read_text(encoding="utf-8"))
    print(f"finished in {time.perf_counter() - started:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
