#!/usr/bin/env python3
"""Build candidate crown polygons from the watershed segmentation."""

from __future__ import annotations

import argparse
import gzip
import json
import math
from pathlib import Path

import numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree

from fresh_urban_forest.city_off_inventory import detect_city_trees


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
    parser.add_argument("--chm", type=Path, default=Path("data/processed/surrey_2025/_chm.tif"))
    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path("data/processed/surrey_2025/off_inventory.geojson.gz"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/surrey_2025/off_inventory_crown_polygons.geojson.gz"),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the full crown-polygon build.

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
    with gzip.open(args.candidates, "rt", encoding="utf-8") as handle:
        candidates = json.load(handle)["features"]
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3157", always_xy=True)
    candidate_xy = []
    candidate_data = []
    for feature in candidates:
        properties = feature["properties"]
        lon, lat = feature["geometry"]["coordinates"]
        x, y = transformer.transform(lon, lat)
        candidate_xy.append((x, y))
        candidate_data.append(
            {
                "candidate_id": str(properties["candidate_id"]),
                "height_m": properties.get("height_m"),
                "confidence": properties.get("confidence"),
                "land_class": properties.get("land_class"),
                "support_class": properties.get("support_class"),
            }
        )
    candidate_tree = cKDTree(np.asarray(candidate_xy, dtype=np.float64))
    detected = detect_city_trees(
        args.chm,
        resolution_m=1.0,
        tile_m=1000.0,
        buffer_m=40.0,
        include_polygons=True,
    )
    collected: dict[str, tuple[float, float]] = {}
    for crown in detected:
        if crown.crown_ring is None or not crown.crown_ring:
            continue
        distance, index = candidate_tree.query(np.asarray([crown.x, crown.y]))
        if not math.isfinite(distance) or distance > 0.5:
            continue
        candidate_id = candidate_data[int(index)]["candidate_id"]
        if candidate_id in collected:
            continue
        ring = [[float(lon), float(lat)] for lon, lat in crown.crown_ring]
        if len(ring) < 4:
            continue
        collected[candidate_id] = (float(crown.x), float(crown.y))
        candidate_data[int(index)]["ring"] = ring
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [row["ring"]]},
            "properties": {
                "candidate_id": row["candidate_id"],
                "height_m": row["height_m"],
                "confidence": row["confidence"],
                "land_class": row["land_class"],
                "support_class": row["support_class"],
            },
        }
        for row in candidate_data
        if "ring" in row
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.output, "wt", encoding="utf-8") as handle:
        json.dump(
            {"type": "FeatureCollection", "features": features},
            handle,
            separators=(",", ":"),
        )
    print(f"candidate polygons: {len(features)} of {len(candidates)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
