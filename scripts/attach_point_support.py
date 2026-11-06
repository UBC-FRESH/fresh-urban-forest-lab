#!/usr/bin/env python3
"""Attach city vegetation point support to the candidate table."""

from __future__ import annotations

import argparse
import gzip
import json
import os
from pathlib import Path


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
        "--support",
        type=Path,
        default=Path("data/processed/vancouver_2022/off_inventory_point_support.json.gz"),
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


def support_class(point_count: int) -> str:
    """Classify a candidate's vegetation point support.

    Parameters
    ----------
    point_count : int
        Vegetation points inside the candidate crown radius.

    Returns
    -------
    str
        ``none``, ``low``, ``medium``, or ``high``.
    """
    if point_count <= 0:
        return "none"
    if point_count < 500:
        return "low"
    if point_count < 1_000:
        return "medium"
    return "high"


def main(argv: list[str] | None = None) -> int:
    """Attach support fields and write the updated candidate layer.

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
    with gzip.open(args.support, "rt", encoding="utf-8") as handle:
        support_rows = json.load(handle)
    support = {str(row["candidate_id"]): row for row in support_rows}
    with gzip.open(args.candidates, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    counts = {"none": 0, "low": 0, "medium": 0, "high": 0}
    missing = 0
    for feature in payload["features"]:
        candidate_id = str(feature["properties"]["candidate_id"])
        row = support.get(candidate_id)
        if row is None:
            missing += 1
            feature["properties"].update(
                {"point_count": None, "point_density": None, "support_class": "none"}
            )
            counts["none"] += 1
            continue
        point_count = int(row["point_count"])
        classification = support_class(point_count)
        feature["properties"].update(
            {
                "point_count": point_count,
                "point_density": float(row["point_density"]),
                "support_class": classification,
            }
        )
        counts[classification] += 1
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    with gzip.open(temporary, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"))
    os.replace(temporary, args.output)
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    summary["point_support"] = {
        "method": (
            "1 m count of LAS classes 3/4/5 inside each candidate crown radius; "
            "four southern-edge candidates lack a matching raw tile."
        ),
        "classes": counts,
        "missing": missing,
        "thresholds": {
            "low": 1,
            "medium": 500,
            "high": 1_000,
        },
        "caveat": (
            "Support is QA evidence. It does not replace the confidence screen; "
            "the default confidence >= 0.6 layer is still the best simple screen."
        ),
    }
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"attached support to {len(payload['features'])} candidates; missing {missing}")
    print(json.dumps(counts, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
