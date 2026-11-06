#!/usr/bin/env python3
"""Aggregate candidate metrics for the Vancouver City tab."""

from __future__ import annotations

import argparse
import gzip
import json
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path

CONFIDENCE_FLOOR = 0.6


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
        "--candidates",
        type=Path,
        default=Path("data/processed/vancouver_2022/off_inventory.geojson.gz"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/vancouver_2022/off_inventory_city_metrics.json"),
    )
    return parser.parse_args(argv)


def _number(value: object) -> float:
    if isinstance(value, (int, float, str)):
        return float(value)
    return 0.0


def _blank() -> dict[str, float]:
    return {
        "candidate_count": 0,
        "high_confidence_count": 0,
        "crown_area_m2": 0.0,
        "crown_volume_m3": 0.0,
        "crown_volume_low_m3": 0.0,
        "crown_volume_high_m3": 0.0,
        "carbon_kg": 0.0,
        "carbon_low_kg": 0.0,
        "carbon_high_kg": 0.0,
    }


def aggregate(features: list[dict[str, object]]) -> dict[str, object]:
    """Aggregate candidate metrics by land proxy and confidence.

    Parameters
    ----------
    features : list of dict
        Candidate GeoJSON features.

    Returns
    -------
    dict
        City-tab metrics.
    """
    classes: dict[str, dict[str, float]] = defaultdict(_blank)
    all_metrics = _blank()
    for feature in features:
        properties = feature.get("properties")
        if not isinstance(properties, Mapping):
            continue
        land = str(properties.get("land_class", "unknown"))
        confidence = _number(properties.get("confidence"))
        target = classes[land]
        high = confidence >= CONFIDENCE_FLOOR
        for metrics in (target, all_metrics):
            metrics["candidate_count"] += 1
            metrics["high_confidence_count"] += int(high)
            metrics["crown_area_m2"] += _number(properties.get("crown_area_m2"))
            metrics["crown_volume_m3"] += _number(properties.get("crown_volume_m3"))
            metrics["crown_volume_low_m3"] += _number(properties.get("crown_volume_low_m3"))
            metrics["crown_volume_high_m3"] += _number(properties.get("crown_volume_high_m3"))
            metrics["carbon_kg"] += _number(properties.get("carbon_kg"))
            metrics["carbon_low_kg"] += _number(properties.get("carbon_low_kg"))
            metrics["carbon_high_kg"] += _number(properties.get("carbon_high_kg"))
    likely_private = classes.get("likely private parcel", _blank())
    return {
        "schema_version": "fresh-urban-forest.off-inventory.city-metrics.v1",
        "confidence_floor": CONFIDENCE_FLOOR,
        "all": {
            key: round(value, 1) if isinstance(value, float) else value
            for key, value in all_metrics.items()
        },
        "likely_private": {
            key: round(value, 1) if isinstance(value, float) else value
            for key, value in likely_private.items()
        },
        "land_classes": {
            name: {
                key: round(value, 1) if isinstance(value, float) else value
                for key, value in metrics.items()
            }
            for name, metrics in sorted(classes.items())
        },
        "methods": {
            "count": "unmatched detected crowns after building/water centre exclusion",
            "crown_area": "sum of segment crown areas; crowns overlap, not unique canopy area",
            "volume": "ellipsoid crown volume; 50% screening envelope",
            "carbon": (
                "Jenkins et al. above-ground biomass with unknown species; 50% screening envelope"
            ),
            "land_proxy": "parcel, park, zoning, and OSM road proxy; not ownership",
        },
        "caveats": [
            "Candidates are not the public tree inventory.",
            "Likely-private is a land proxy, not ownership or access.",
            "Crown area is summed per candidate and can overlap.",
            "Volume and carbon are screening models with unknown species.",
            "Candidate count uncertainty is reported in the P32 validation report.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    """Build the city-tab candidate metrics.

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
        features = json.load(handle)["features"]
    payload = aggregate(features)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"likely_private": payload["likely_private"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
