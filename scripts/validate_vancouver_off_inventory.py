#!/usr/bin/env python3
"""Validate the city off-inventory screening layer on fixed held-out samples."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import Counter
from pathlib import Path

import geopandas as gpd
import rasterio
from shapely.geometry import Point

from fresh_urban_forest.city_validation import (
    audit_sample_json,
    evaluate_public_recall,
    sample_candidate_audit,
    sample_public_trees,
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
    parser.add_argument(
        "--detected",
        type=Path,
        default=Path("data/processed/vancouver_2022/detected_city.json.gz"),
    )
    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path("data/processed/vancouver_2022/off_inventory.geojson.gz"),
    )
    parser.add_argument(
        "--local-areas",
        type=Path,
        default=Path("data/raw/vancouver/local_area_boundary.geojson"),
    )
    parser.add_argument(
        "--orthophoto-index",
        type=Path,
        default=Path("data/raw/vancouver/orthophoto-imagery-2022.geojson"),
    )
    parser.add_argument("--chm", type=Path, default=Path("data/processed/vancouver_2022/chm.tif"))
    return parser.parse_args(argv)


def load_trees(path: Path) -> tuple[TreeRecord, ...]:
    """Load the enriched public-tree inventory.

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
    """Load detected crowns from the detection cache.

    Parameters
    ----------
    path : Path
        Compressed JSON detection cache.

    Returns
    -------
    tuple of DetectedTree
        Detected crowns.
    """
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return tuple(DetectedTree(**item) for item in json.load(handle))


def load_candidates(path: Path) -> tuple[dict[str, object], ...]:
    """Load candidate GeoJSON features.

    Parameters
    ----------
    path : Path
        Compressed candidate GeoJSON.

    Returns
    -------
    tuple of dict
        Candidate features.
    """
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    return tuple(payload["features"])


def attach_orthophoto_tiles(
    sample: tuple[dict[str, object], ...],
    index_path: Path,
) -> tuple[dict[str, object], ...]:
    """Attach orthophoto tile names and URLs to audit rows.

    Parameters
    ----------
    sample : tuple of dict
        Candidate audit rows with ``lon`` and ``lat``.
    index_path : Path
        City orthophoto tile index.

    Returns
    -------
    tuple of dict
        Rows with tile metadata.
    """
    if not sample:
        return ()
    index = gpd.read_file(index_path)
    points = gpd.GeoDataFrame(
        {"index": list(range(len(sample)))},
        geometry=[
            Point(float(row["lon"]), float(row["lat"]))  # type: ignore[arg-type]
            for row in sample
        ],
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(points, index, how="left", predicate="within")
    joined = joined[~joined.index.duplicated(keep="first")]
    enriched: list[dict[str, object]] = []
    for index_value, row in enumerate(sample):
        hit = joined.loc[index_value] if index_value in joined.index else None
        enriched.append(
            {
                **row,
                "orthophoto_tile": str(hit["name"]) if hit is not None else "",
                "mrsid_url": str(hit["mrsid_url"]) if hit is not None else "",
                "ecw_url": str(hit["ecw_url"]) if hit is not None else "",
            }
        )
    return tuple(enriched)


def write_audit_files(
    sample: tuple[dict[str, object], ...],
    out_dir: Path,
) -> None:
    """Write the audit CSV, GeoJSON, and summary JSON.

    Parameters
    ----------
    sample : tuple of dict
        Candidate audit rows.
    out_dir : Path
        Destination directory.
    """
    csv_path = out_dir / "off_inventory_audit_sample.csv"
    fields = [
        "candidate_id",
        "confidence_band",
        "confidence",
        "land_class",
        "local_area",
        "height_m",
        "crown_radius_m",
        "lon",
        "lat",
        "orthophoto_tile",
        "mrsid_url",
        "ecw_url",
        "audit_label",
        "audit_notes",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in sample:
            writer.writerow({field: row.get(field, "") for field in fields})
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
            "properties": {key: value for key, value in row.items() if key not in {"lon", "lat"}},
        }
        for row in sample
    ]
    with (out_dir / "off_inventory_audit_sample.geojson").open("w", encoding="utf-8") as handle:
        json.dump({"type": "FeatureCollection", "features": features}, handle, indent=2)
    with (out_dir / "off_inventory_audit_sample.json").open("w", encoding="utf-8") as handle:
        json.dump(audit_sample_json(sample), handle, indent=2)


def main(argv: list[str] | None = None) -> int:
    """Run the fixed held-out validation and audit packet.

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
    trees = load_trees(args.trees)
    detected = load_detected(args.detected)
    local_areas = gpd.read_file(args.local_areas).to_crs("EPSG:3157")
    with rasterio.open(args.chm) as dataset:
        left, bottom, right, top = dataset.bounds
        bounds = (float(left), float(bottom), float(right), float(top))
    sample = sample_public_trees(trees, local_areas, bounds)
    recall = evaluate_public_recall(sample, detected)
    candidates = load_candidates(args.candidates)
    audit = sample_candidate_audit(candidates, local_areas, bounds)
    audit = attach_orthophoto_tiles(audit, args.orthophoto_index)
    write_audit_files(audit, args.root)
    report = {
        "schema_version": "fresh-urban-forest.off-inventory.validation.v1",
        "dataset_id": "vancouver-city-2022",
        "status": (
            "held-out public recall complete; candidate precision pending orthophoto "
            "inspection; independent UBC test pending"
        ),
        "bounds": list(bounds),
        "public_tree_recall": recall,
        "candidate_audit": {
            "sample_size": len(audit),
            "confidence_bands": dict(
                sorted(Counter(str(row["confidence_band"]) for row in audit).items())
            ),
            "land_classes": dict(sorted(Counter(str(row["land_class"]) for row in audit).items())),
            "tile_count": len({row["orthophoto_tile"] for row in audit if row["orthophoto_tile"]}),
            "status": "packet prepared; imagery inspection pending",
        },
        "exclusions": {
            "unknown_local_area": "excluded from the public-tree sample",
            "block_buffer_m": 100.0,
            "block_size_m": 500.0,
        },
    }
    report_path = args.root / "off_inventory_validation.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
