#!/usr/bin/env python3
"""Attach method-labelled attribute uncertainty to the candidate table."""

from __future__ import annotations

import argparse
import gzip
import json
import os
from pathlib import Path

HEIGHT_LOW = 0.8
HEIGHT_HIGH = 1.2
CROWN_LOW = 0.75
CROWN_HIGH = 1.25
DBH_LOW = 0.65
DBH_HIGH = 1.35
VOLUME_LOW = 0.5
VOLUME_HIGH = 1.5
CARBON_LOW = 0.5
CARBON_HIGH = 1.5


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
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/vancouver_2022/off_inventory.geojson.gz"),
    )
    return parser.parse_args(argv)


def _as_float(value: object) -> float:
    if isinstance(value, (int, float, str)):
        return float(value)
    return 0.0


def attribute_envelope(properties: dict[str, object]) -> dict[str, object]:
    """Build method-labelled uncertainty fields for one candidate.

    Parameters
    ----------
    properties : dict
        Candidate properties containing height, crown, DBH, volume, and carbon.

    Returns
    -------
    dict
        Additional uncertainty fields.
    """
    height = _as_float(properties.get("height_m"))
    radius = _as_float(properties.get("crown_radius_m"))
    dbh = _as_float(properties.get("dbh_cm"))
    volume = _as_float(properties.get("crown_volume_m3"))
    carbon = _as_float(properties.get("carbon_kg"))
    return {
        "height_low_m": round(height * HEIGHT_LOW, 2),
        "height_high_m": round(height * HEIGHT_HIGH, 2),
        "crown_radius_low_m": round(radius * CROWN_LOW, 2),
        "crown_radius_high_m": round(radius * CROWN_HIGH, 2),
        "dbh_low_cm": round(dbh * DBH_LOW, 1),
        "dbh_high_cm": round(dbh * DBH_HIGH, 1),
        "crown_volume_low_m3": round(volume * VOLUME_LOW, 1),
        "crown_volume_high_m3": round(volume * VOLUME_HIGH, 1),
        "carbon_low_kg": round(carbon * CARBON_LOW, 1),
        "carbon_high_kg": round(carbon * CARBON_HIGH, 1),
        "attribute_evidence": "lidar_screening; allometric_unknown_species",
    }


def main(argv: list[str] | None = None) -> int:
    """Attach attribute ranges and write the updated candidate layer.

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
    totals = {
        "height_low_m": 0.0,
        "height_high_m": 0.0,
        "crown_volume_low_m3": 0.0,
        "crown_volume_high_m3": 0.0,
        "carbon_low_kg": 0.0,
        "carbon_high_kg": 0.0,
    }
    for feature in payload["features"]:
        properties = feature["properties"]
        properties.update(attribute_envelope(properties))
        for key in totals:
            totals[key] += _as_float(properties[key])
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    with gzip.open(temporary, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"))
    os.replace(temporary, args.output)
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    summary["attribute_schema"] = {
        "height": {
            "field": "height_m",
            "unit": "m",
            "method": "ALS 2 m block-max CHM segment peak",
            "evidence_tier": "lidar_screening",
            "range": [HEIGHT_LOW, HEIGHT_HIGH],
        },
        "crown_radius": {
            "field": "crown_radius_m",
            "unit": "m",
            "method": "watershed segment equivalent radius",
            "evidence_tier": "lidar_screening",
            "range": [CROWN_LOW, CROWN_HIGH],
        },
        "dbh": {
            "field": "dbh_cm",
            "unit": "cm",
            "method": "height-to-DBH allometry with unknown species",
            "evidence_tier": "allometric_screening",
            "range": [DBH_LOW, DBH_HIGH],
        },
        "crown_volume": {
            "field": "crown_volume_m3",
            "unit": "m3",
            "method": "ellipsoid crown volume from CHM height and segment width",
            "evidence_tier": "allometric_screening",
            "range": [VOLUME_LOW, VOLUME_HIGH],
        },
        "carbon": {
            "field": "carbon_kg",
            "unit": "kg",
            "method": "Jenkins et al. above-ground biomass, species unknown",
            "evidence_tier": "allometric_screening",
            "range": [CARBON_LOW, CARBON_HIGH],
        },
        "range_kind": "screening envelope, not a calibrated confidence interval",
    }
    summary["attribute_totals"] = {
        "height_low_m": round(totals["height_low_m"], 1),
        "height_high_m": round(totals["height_high_m"], 1),
        "crown_volume_low_m3": round(totals["crown_volume_low_m3"], 1),
        "crown_volume_high_m3": round(totals["crown_volume_high_m3"], 1),
        "carbon_low_kg": round(totals["carbon_low_kg"], 1),
        "carbon_high_kg": round(totals["carbon_high_kg"], 1),
    }
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary["attribute_totals"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
