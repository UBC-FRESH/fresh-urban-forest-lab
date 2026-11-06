#!/usr/bin/env python3
"""Build per-candidate vegetation point support from the City LAS tiles."""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import laspy
import numpy as np
from pyproj import Transformer

from fresh_urban_forest.city import VEGETATION_CLASSES
from fresh_urban_forest.point_support import support_rows, tile_id, tile_origin


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
        "--raw-dir",
        type=Path,
        default=Path("data/raw/city_lidar/2022"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/vancouver_2022/off_inventory_point_support.json.gz"),
    )
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--limit", type=int, default=0)
    return parser.parse_args(argv)


def load_candidates(path: Path) -> dict[str, list[dict[str, object]]]:
    """Group candidate features by 1 km tile.

    Parameters
    ----------
    path : Path
        Compressed candidate GeoJSON.

    Returns
    -------
    dict
        Candidate rows keyed by tile identifier.
    """
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3157", always_xy=True)
    grouped: dict[str, list[dict[str, object]]] = {}
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    for feature in payload["features"]:
        properties = feature["properties"]
        lon, lat = feature["geometry"]["coordinates"]
        x, y = transformer.transform(lon, lat)
        tile = tile_id(x, y)
        grouped.setdefault(tile, []).append(
            {
                "candidate_id": str(properties["candidate_id"]),
                "x_m": float(x),
                "y_m": float(y),
                "crown_radius_m": float(properties.get("crown_radius_m", 0.0)),
                "height_m": float(properties.get("height_m", 0.0)),
                "confidence": float(properties.get("confidence", 0.0)),
                "land_class": str(properties.get("land_class", "unknown")),
            }
        )
    return grouped


def count_tile(zip_path: Path, tile: str, scratch_dir: Path) -> np.ndarray:
    """Rasterise vegetation points in one City tile at 1 m.

    Parameters
    ----------
    zip_path : Path
        City LAS ZIP.
    tile : str
        Tile identifier.
    scratch_dir : Path
        Temporary extraction path.

    Returns
    -------
    numpy.ndarray
        ``1000 x 1000`` vegetation point count grid.
    """
    left, bottom = tile_origin(tile)
    scratch_dir.mkdir(parents=True, exist_ok=True)
    target = scratch_dir / f"{tile}.las"
    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = [
                name for name in archive.namelist() if name.lower().endswith((".las", ".laz"))
            ]
            if not members:
                return np.zeros((1000, 1000), dtype=np.uint32)
            with archive.open(members[0]) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)
        counts = np.zeros((1000, 1000), dtype=np.uint32)
        with laspy.open(target) as reader:
            for points in reader.chunk_iterator(2_000_000):
                classes = np.asarray(points.classification)
                vegetation = np.isin(classes, VEGETATION_CLASSES)
                if not vegetation.any():
                    continue
                x = np.asarray(points.x)[vegetation]
                y = np.asarray(points.y)[vegetation]
                cols = np.floor(x - left).astype(np.int64)
                rows = np.floor(y - bottom).astype(np.int64)
                valid = (cols >= 0) & (cols < 1000) & (rows >= 0) & (rows < 1000)
                if not valid.any():
                    continue
                flat = rows[valid] * 1000 + cols[valid]
                counts += (
                    np.bincount(flat, minlength=1_000_000).reshape(1000, 1000).astype(np.uint32)
                )
        return counts
    finally:
        target.unlink(missing_ok=True)


def process_tile(
    tile: str,
    zip_path: Path,
    candidates: list[dict[str, object]],
    scratch_root: Path,
) -> tuple[str, list[dict[str, object]]]:
    """Compute support for all candidates in one tile.

    Parameters
    ----------
    tile : str
        Tile identifier.
    zip_path : Path
        City LAS ZIP.
    candidates : list of dict
        Candidate rows in the tile.
    scratch_root : Path
        Temporary extraction root.

    Returns
    -------
    tuple of str and list of dict
        Tile identifier and support rows.
    """
    left, bottom = tile_origin(tile)
    counts = count_tile(zip_path, tile, scratch_root / tile)
    return tile, support_rows(counts, candidates, left=left, bottom=bottom)


def main(argv: list[str] | None = None) -> int:
    """Run the full point-support build.

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
    grouped = load_candidates(args.candidates)
    tiles = sorted(grouped)
    if args.limit > 0:
        tiles = tiles[: args.limit]
    scratch_root = Path("data/tmp/point_support_las")
    scratch_root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    with ProcessPoolExecutor(max_workers=max(1, args.jobs)) as executor:
        futures = {}
        for tile in tiles:
            zip_path = args.raw_dir / f"{tile}.zip"
            if not zip_path.exists():
                continue
            futures[executor.submit(process_tile, tile, zip_path, grouped[tile], scratch_root)] = (
                tile
            )
        for completed, future in enumerate(as_completed(futures), start=1):
            tile, tile_rows = future.result()
            rows.extend(tile_rows)
            print(f"[{completed}/{len(futures)}] {tile}: {len(tile_rows)} candidates", flush=True)
    rows.sort(key=lambda row: str(row["candidate_id"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.output, "wt", encoding="utf-8") as handle:
        json.dump(rows, handle, separators=(",", ":"))
    print(f"wrote {len(rows)} candidate support rows to {args.output}")
    shutil.rmtree(scratch_root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
