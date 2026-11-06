#!/usr/bin/env python3
"""Build compact high-confidence candidate arrays for the 3D scene."""

from __future__ import annotations

import argparse
import gzip
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from pyproj import Transformer

LAND_CODES = {
    "likely private parcel": 0,
    "street/lane": 1,
    "public park": 2,
    "other parcel": 3,
    "unknown": 4,
}
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
        default=Path("data/processed/vancouver_2022/off_inventory_3d.json.gz"),
    )
    return parser.parse_args(argv)


def _number(value: object) -> float:
    if isinstance(value, (int, float, str)):
        return float(value)
    return 0.0


def compact_payload(features: list[dict[str, object]]) -> dict[str, object]:
    """Build compact arrays for the 3D candidate overlay.

    Parameters
    ----------
    features : list of dict
        Candidate GeoJSON features.

    Returns
    -------
    dict
        Arrays aligned by candidate index.
    """
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3157", always_xy=True)
    arrays: dict[str, list[object]] = {
        "candidate_id": [],
        "x_m": [],
        "y_m": [],
        "height_m": [],
        "crown_radius_m": [],
        "crown_area_m2": [],
        "dbh_cm": [],
        "crown_volume_m3": [],
        "carbon_kg": [],
        "confidence": [],
        "point_count": [],
        "land_code": [],
    }
    for feature in features:
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(properties, Mapping) or not isinstance(geometry, Mapping):
            continue
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, Sequence) or len(coordinates) < 2:
            continue
        confidence = _number(properties.get("confidence"))
        if confidence < CONFIDENCE_FLOOR:
            continue
        if _number(properties.get("crown_radius_m")) > 25.0:
            continue
        lon = float(coordinates[0])
        lat = float(coordinates[1])
        x, y = transformer.transform(lon, lat)
        arrays["candidate_id"].append(str(properties["candidate_id"]))
        arrays["x_m"].append(round(x, 2))
        arrays["y_m"].append(round(y, 2))
        arrays["height_m"].append(round(_number(properties.get("height_m")), 2))
        arrays["crown_radius_m"].append(round(_number(properties.get("crown_radius_m")), 2))
        arrays["crown_area_m2"].append(round(_number(properties.get("crown_area_m2")), 1))
        arrays["dbh_cm"].append(round(_number(properties.get("dbh_cm")), 1))
        arrays["crown_volume_m3"].append(round(_number(properties.get("crown_volume_m3")), 1))
        arrays["carbon_kg"].append(round(_number(properties.get("carbon_kg")), 1))
        arrays["confidence"].append(round(confidence, 4))
        arrays["point_count"].append(int(_number(properties.get("point_count"))))
        arrays["land_code"].append(LAND_CODES.get(str(properties.get("land_class")), 4))
    return {
        "schema_version": "fresh-urban-forest.off-inventory.3d.v2",
        "count": len(arrays["candidate_id"]),
        "confidence_floor": CONFIDENCE_FLOOR,
        **arrays,
    }


def main(argv: list[str] | None = None) -> int:
    """Build the compact 3D candidate payload.

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
    payload = compact_payload(features)
    with gzip.open(args.output, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"))
    print(f"wrote {payload['count']} 3D candidates to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
