#!/usr/bin/env python3
"""Remove implausibly large watershed crowns from the candidate table."""

from __future__ import annotations

import argparse
import gzip
import json
import os
from collections import Counter
from pathlib import Path

MAX_CROWN_RADIUS_M = 25.0


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
        "--summary",
        type=Path,
        default=Path("data/processed/vancouver_2022/off_inventory.json"),
    )
    parser.add_argument("--max-radius", type=float, default=MAX_CROWN_RADIUS_M)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/vancouver_2022/off_inventory.geojson.gz"),
    )
    return parser.parse_args(argv)


def _number(value: object) -> float:
    if isinstance(value, (int, float, str)):
        return float(value)
    return 0.0


def main(argv: list[str] | None = None) -> int:
    """Filter oversized crowns and recompute the summary.

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
        payload = json.load(handle)
    kept = []
    removed = 0
    for feature in payload["features"]:
        radius = _number(feature["properties"].get("crown_radius_m"))
        if radius > args.max_radius:
            removed += 1
            continue
        kept.append(feature)
    payload["features"] = kept
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    with gzip.open(temporary, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"))
    os.replace(temporary, args.output)
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    land_classes = Counter(
        str(feature["properties"].get("land_class", "unknown")) for feature in kept
    )
    support_classes = Counter(
        str(feature["properties"].get("support_class", "none")) for feature in kept
    )
    confidence = sorted(_number(feature["properties"].get("confidence")) for feature in kept)
    totals = {
        "candidate_area_m2": 0.0,
        "candidate_canopy_volume_m3": 0.0,
        "candidate_carbon_kg": 0.0,
        "height_low_m": 0.0,
        "height_high_m": 0.0,
        "crown_volume_low_m3": 0.0,
        "crown_volume_high_m3": 0.0,
        "carbon_low_kg": 0.0,
        "carbon_high_kg": 0.0,
    }
    for feature in kept:
        properties = feature["properties"]
        totals["candidate_area_m2"] += _number(properties.get("crown_area_m2"))
        totals["candidate_canopy_volume_m3"] += _number(properties.get("crown_volume_m3"))
        totals["candidate_carbon_kg"] += _number(properties.get("carbon_kg"))
        totals["height_low_m"] += _number(properties.get("height_low_m"))
        totals["height_high_m"] += _number(properties.get("height_high_m"))
        totals["crown_volume_low_m3"] += _number(properties.get("crown_volume_low_m3"))
        totals["crown_volume_high_m3"] += _number(properties.get("crown_volume_high_m3"))
        totals["carbon_low_kg"] += _number(properties.get("carbon_low_kg"))
        totals["carbon_high_kg"] += _number(properties.get("carbon_high_kg"))
    summary["candidate_count"] = len(kept)
    summary["high_confidence_count"] = sum(
        1 for feature in kept if _number(feature["properties"].get("confidence")) >= 0.6
    )
    summary["candidate_area_m2"] = round(totals["candidate_area_m2"], 1)
    summary["candidate_canopy_volume_m3"] = round(totals["candidate_canopy_volume_m3"], 1)
    summary["candidate_carbon_kg"] = round(totals["candidate_carbon_kg"], 1)
    summary["land_classes"] = dict(sorted(land_classes.items()))
    summary["confidence_p50"] = round(confidence[len(confidence) // 2], 3) if confidence else 0.0
    summary["confidence_p95"] = (
        round(confidence[int(len(confidence) * 0.95)], 3) if confidence else 0.0
    )
    summary["outlier_filter"] = {
        "max_crown_radius_m": args.max_radius,
        "removed": removed,
        "reason": "watershed flood segments with implausible crown radius",
    }
    if "point_support" in summary:
        summary["point_support"]["classes"] = {
            key: int(support_classes.get(key, 0)) for key in ("none", "low", "medium", "high")
        }
    if "attribute_totals" in summary:
        summary["attribute_totals"] = {
            key: round(totals[key], 1) for key in summary["attribute_totals"]
        }
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"kept {len(kept)} candidates; removed {removed} oversized crowns")
    print(json.dumps(summary["land_classes"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
