#!/usr/bin/env python3
"""Estimate a vertical control offset from 2018 ground points and the 2022 DEM.

The estimate uses class-2 ground points on open ground, not canopy. It is a screening
control estimate, not survey-grade validation or a citywide accuracy assessment.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path

import laspy
import numpy as np
import rasterio
from numpy.typing import NDArray
from rasterio.transform import rowcol
from rasterio.windows import from_bounds

from fresh_urban_forest.vertical_control import estimate_control_offset

DEFAULT_DATASET = Path(
    "/srv/shared-data/gep/ws4/fresh-urban-forest-lab/data/processed/vancouver_2022"
)
DEFAULT_TILES = Path("data/raw/tiles")


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
    parser.add_argument("--tiles", type=Path, default=DEFAULT_TILES)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--out", type=Path, default=Path("data/processed/vertical_control.json"))
    parser.add_argument("--stride", type=int, default=8)
    parser.add_argument("--max-abs-m", type=float, default=10.0)
    parser.add_argument("--bootstrap-samples", type=int, default=2_000)
    return parser.parse_args(argv)


def _tile_differences(
    las_path: Path,
    *,
    dem_path: Path,
    chm_path: Path,
    building_path: Path,
    stride: int,
    max_abs_m: float,
) -> NDArray[np.float64]:
    """Extract class-2 ground differences for one LAS tile."""
    with (
        rasterio.open(dem_path) as dem,
        rasterio.open(chm_path) as chm,
        rasterio.open(building_path) as building,
        laspy.open(las_path) as source,
    ):
        header = source.header
        minx, miny = float(header.mins[0]), float(header.mins[1])
        maxx, maxy = float(header.maxs[0]), float(header.maxs[1])
        left = max(minx, dem.bounds.left)
        bottom = max(miny, dem.bounds.bottom)
        right = min(maxx, dem.bounds.right)
        top = min(maxy, dem.bounds.top)
        if right <= left or top <= bottom:
            return np.empty(0, dtype=np.float64)
        window = (
            from_bounds(left, bottom, right, top, dem.transform).round_offsets().round_lengths()
        )
        dem_array = dem.read(1, window=window).astype(np.float64)
        chm_array = chm.read(1, window=window).astype(np.float64)
        building_array = building.read(1, window=window).astype(np.float64)
        col_offset = int(window.col_off)
        row_offset = int(window.row_off)
        differences: list[NDArray[np.float64]] = []
        for points in source.chunk_iterator(2_000_000):
            x = np.asarray(points.x)[::stride]
            y = np.asarray(points.y)[::stride]
            z = np.asarray(points.z)[::stride]
            classes = np.asarray(points.classification)[::stride]
            rows, cols = rowcol(dem.transform, x, y)
            local_rows = np.asarray(rows) - row_offset
            local_cols = np.asarray(cols) - col_offset
            inside = (
                (local_rows >= 0)
                & (local_rows < dem_array.shape[0])
                & (local_cols >= 0)
                & (local_cols < dem_array.shape[1])
            )
            ground = inside & (classes == 2)
            if not np.any(ground):
                continue
            ground_dem = dem_array[local_rows[ground], local_cols[ground]]
            ground_chm = chm_array[local_rows[ground], local_cols[ground]]
            ground_building = building_array[local_rows[ground], local_cols[ground]]
            keep = (
                np.isfinite(ground_dem)
                & np.isfinite(ground_chm)
                & (ground_chm <= 1.0)
                & (ground_building == 0)
                & (np.abs(z[ground] - ground_dem) <= max_abs_m)
            )
            if np.any(keep):
                differences.append(z[ground][keep] - ground_dem[keep])
    if not differences:
        return np.empty(0, dtype=np.float64)
    return np.concatenate(differences)


def run(args: argparse.Namespace) -> dict[str, object]:
    """Run the control estimate and write a JSON summary.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments.

    Returns
    -------
    dict
        Estimate, tile summaries, and output path.
    """
    if args.stride < 1:
        raise ValueError("stride must be positive")
    tiles = sorted(args.tiles.glob("*.zip"))
    if not tiles:
        raise FileNotFoundError(f"no zip tiles under {args.tiles}")
    all_values: list[NDArray[np.float64]] = []
    tile_rows: list[dict[str, object]] = []
    for zip_path in tiles:
        with tempfile.TemporaryDirectory(prefix="p50_las_") as temporary:
            with zipfile.ZipFile(zip_path) as archive:
                members = [name for name in archive.namelist() if name.lower().endswith(".las")]
                if not members:
                    continue
                archive.extract(members[0], temporary)
                las_path = Path(temporary) / members[0]
            values = _tile_differences(
                las_path,
                dem_path=args.dataset / "dem.tif",
                chm_path=args.dataset / "chm.tif",
                building_path=args.dataset / "building_mask.tif",
                stride=args.stride,
                max_abs_m=args.max_abs_m,
            )
        if values.size:
            all_values.append(values)
            tile_rows.append(
                {
                    "tile": zip_path.name,
                    "count": int(values.size),
                    "median_m": round(float(np.median(values)), 4),
                }
            )
    if not all_values:
        raise ValueError("no control observations found")
    estimate = estimate_control_offset(
        np.concatenate(all_values),
        surface="2018-class2-ground-vs-2022-dem",
        bootstrap_samples=args.bootstrap_samples,
    )
    payload: dict[str, object] = {
        "schema_version": "fresh-urban-forest.vertical-control.v1",
        "dataset_id": "vancouver-city-2022",
        "method": "2018 class-2 ground versus 2022 DEM",
        "stride": args.stride,
        "max_abs_m": args.max_abs_m,
        "tiles": tile_rows,
        "estimate": estimate.to_dict(),
        "caveats": [
            "Class-2 ground points are a stable-surface proxy, not survey control.",
            "Ground can be excavated, filled, or reclassified between acquisitions.",
            "No canopy, tree, or model value was used as control.",
            "The sample is not a citywide probability sample; do not overstate coverage.",
            "This is not a survey-grade accuracy assessment.",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {"estimate": payload["estimate"], "tile_count": len(tile_rows), "out": str(args.out)}


def main(argv: list[str] | None = None) -> int:
    """Run the Vancouver vertical-control estimate.

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
    result = run(args)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
