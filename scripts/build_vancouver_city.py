#!/usr/bin/env python3
"""Rasterise the full City of Vancouver 2022 LiDAR and build the city mosaic.

The operator first acquires the 181 City ZIP tiles with
``scripts/browser_download_tiles.py``. This script extracts one LAS at a time, writes a
compressed 1 m tile, and mosaics the completed tiles into the city pack.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from fresh_urban_forest.city import (
    build_city_mosaic,
    rasterize_zip_tile,
    save_city_tile,
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
        "--manifest",
        type=Path,
        default=Path("data/raw/tiles/vancouver_2022_city.json"),
        help="City LiDAR tile manifest",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw/city_lidar/2022"),
        help="Directory of downloaded City ZIP tiles",
    )
    parser.add_argument(
        "--tiles-dir",
        type=Path,
        default=Path("data/processed/vancouver_2022/tiles"),
        help="Directory for rasterised tile NPZ files",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/processed/vancouver_2022"),
        help="Directory for the city mosaic",
    )
    parser.add_argument(
        "--aoi",
        type=Path,
        default=Path("data/raw/vancouver/local_area_boundary.geojson"),
        help="City AOI polygon GeoJSON",
    )
    parser.add_argument(
        "--scratch-dir",
        type=Path,
        default=Path("data/tmp/las"),
        help="Directory for temporary LAS extraction",
    )
    parser.add_argument("--jobs", type=int, default=4, help="Parallel tile workers")
    parser.add_argument("--limit", type=int, default=0, help="Process at most N tiles")
    parser.add_argument("--overwrite", action="store_true", help="Rebuild existing tiles")
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Fail unless every manifest tile has a rasterised NPZ",
    )
    parser.add_argument(
        "--skip-mosaic",
        action="store_true",
        help="Only rasterise tiles; do not build the mosaic",
    )
    return parser.parse_args(argv)


def process_tile(
    tile_id: str,
    zip_path: Path,
    tiles_dir: Path,
    scratch_dir: Path,
) -> tuple[str, int]:
    """Rasterise and save one tile.

    Parameters
    ----------
    tile_id : str
        Tile identifier.
    zip_path : Path
        Downloaded City ZIP.
    tiles_dir : Path
        Directory for rasterised NPZs.
    scratch_dir : Path
        Temporary LAS extraction root.

    Returns
    -------
    tuple of str and int
        Tile identifier and output byte size.
    """
    scratch = scratch_dir / tile_id
    try:
        tile = rasterize_zip_tile(
            zip_path,
            scratch_dir=scratch,
            crs_override="EPSG:3157",
        )
        output = save_city_tile(tile, tiles_dir / f"{tile_id}.npz")
        return tile_id, output.stat().st_size
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def load_tiles(manifest_path: Path, raw_dir: Path, limit: int) -> list[tuple[str, Path]]:
    """Load and filter the manifest to available ZIP tiles.

    Parameters
    ----------
    manifest_path : Path
        Tile manifest JSON.
    raw_dir : Path
        Directory of ZIP tiles.
    limit : int
        Maximum number of tiles; zero means all.

    Returns
    -------
    list of tuple of str and Path
        Tile identifiers and ZIP paths.
    """
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    tiles: list[tuple[str, Path]] = []
    for item in payload.get("tiles", []):
        if not isinstance(item, dict):
            continue
        tile_id = str(item.get("tile_id", ""))
        filename = str(item.get("filename", ""))
        if not tile_id or not filename:
            continue
        path = raw_dir / filename
        if path.exists() and path.stat().st_size > 0:
            tiles.append((tile_id, path))
    if limit > 0:
        tiles = tiles[:limit]
    return tiles


def main(argv: list[str] | None = None) -> int:
    """Run the city rasterisation and mosaic.

    Parameters
    ----------
    argv : list of str or None
        Command-line arguments.

    Returns
    -------
    int
        Zero on success.
    """
    args = parse_args(argv)
    tiles = load_tiles(args.manifest, args.raw_dir, args.limit)
    if not tiles:
        print("no downloaded tiles found", file=sys.stderr)
        return 1
    args.tiles_dir.mkdir(parents=True, exist_ok=True)
    args.scratch_dir.mkdir(parents=True, exist_ok=True)
    pending: list[tuple[str, Path]] = []
    for tile_id, zip_path in tiles:
        output = args.tiles_dir / f"{tile_id}.npz"
        if output.exists() and output.stat().st_size > 0 and not args.overwrite:
            continue
        pending.append((tile_id, zip_path))
    print(f"manifest tiles available: {len(tiles)}; to process: {len(pending)}")
    with ProcessPoolExecutor(max_workers=max(1, args.jobs)) as executor:
        futures = {
            executor.submit(
                process_tile,
                tile_id,
                zip_path,
                args.tiles_dir,
                args.scratch_dir,
            ): tile_id
            for tile_id, zip_path in pending
        }
        completed = 0
        for future in as_completed(futures):
            tile_id = futures[future]
            try:
                _, size = future.result()
            except Exception as exc:  # pragma: no cover - operator path
                print(f"failed {tile_id}: {exc}", file=sys.stderr)
                continue
            completed += 1
            print(f"[{completed}/{len(pending)}] {tile_id} -> {size / 1e6:.1f} MB")
    available = sorted(args.tiles_dir.glob("*.npz"))
    print(f"rasterised tiles present: {len(available)}")
    if args.require_complete and len(available) < len(tiles):
        print(
            f"incomplete: {len(available)} of {len(tiles)} manifest tiles",
            file=sys.stderr,
        )
        return 1
    if args.skip_mosaic:
        return 0
    if not available:
        print("no rasterised tiles to mosaic", file=sys.stderr)
        return 1
    summary = build_city_mosaic(
        available,
        aoi_path=args.aoi,
        out_dir=args.out_dir,
    )
    print(
        f"mosaic: {summary.width}x{summary.height} at {summary.resolution_m} m, "
        f"{summary.tile_count} tiles, coverage {summary.coverage_fraction:.3f}, "
        f"CHM p50 {summary.chm_p50_m:.2f} m, p95 {summary.chm_p95_m:.2f} m"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
