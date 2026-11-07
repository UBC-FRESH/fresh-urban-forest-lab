#!/usr/bin/env python3
"""Build a Vancouver Landsat LST and heat-equity screen.

The script reads public Landsat Collection 2 Level-2 scenes downloaded from the
Microsoft Planetary Computer and the P38 social-equity cells. It does not use a
proprietary tree-equity index or a CanopyFit code path.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import cast

import numpy as np
import rasterio
from numpy.typing import NDArray
from rasterio.enums import Resampling

from fresh_urban_forest.heat_equity import (
    HEAT_EQUITY_EVIDENCE,
    LST_EVIDENCE,
    LST_OFFSET_K,
    LST_SCALE,
    build_heat_equity_grid,
    composite_lst,
    read_landsat_lst,
    write_heat_equity_product,
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
        "--root",
        type=Path,
        default=Path("data/processed/vancouver_2022"),
        help="P30 city dataset directory with masks",
    )
    parser.add_argument(
        "--landsat-dir",
        type=Path,
        default=Path("data/raw/landsat_2022"),
        help="Directory with download_manifest.json and scene folders",
    )
    parser.add_argument(
        "--heat-priority",
        type=Path,
        default=Path("data/processed/vancouver_2022/heat_priority.json"),
        help="P38 heat-priority JSON",
    )
    parser.add_argument("--out", type=Path, default=None, help="Output directory")
    parser.add_argument("--resolution", type=float, default=30.0, help="LST cell size")
    parser.add_argument("--cell-size", type=float, default=400.0, help="Analysis cell size")
    return parser.parse_args(argv)


def target_shape(
    bounds: tuple[float, float, float, float],
    resolution: float,
) -> tuple[int, int]:
    """Return the LST grid shape.

    Parameters
    ----------
    bounds : tuple of float
        ``(left, bottom, right, top)``.
    resolution : float
        Cell size in metres.

    Returns
    -------
    tuple of int
        ``(height, width)``.

    Raises
    ------
    ValueError
        When the bounds or resolution are invalid.
    """
    left, bottom, right, top = bounds
    if right <= left or top <= bottom or resolution <= 0.0:
        raise ValueError("bounds and resolution must be positive")
    return (
        max(1, math.ceil((top - bottom) / resolution)),
        max(1, math.ceil((right - left) / resolution)),
    )


def read_mask(path: Path, shape: tuple[int, int]) -> NDArray[np.bool_]:
    """Read a mask at a target shape, treating nodata as false.

    Parameters
    ----------
    path : Path
        Mask path.
    shape : tuple of int
        Target shape.

    Returns
    -------
    numpy.ndarray
        Boolean mask.
    """
    with rasterio.open(path) as dataset:
        array = dataset.read(1, out_shape=shape, resampling=Resampling.nearest)
        nodata = dataset.nodata
    mask = array > 0
    if nodata is not None:
        mask &= array != nodata
    return np.asarray(mask, dtype=np.bool_)


def load_priority(path: Path) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    """Load P38 cells and metadata.

    Parameters
    ----------
    path : Path
        P38 heat-priority JSON.

    Returns
    -------
    tuple of dict and dict
        Cells keyed by id and the product metadata.

    Raises
    ------
    FileNotFoundError
        When the P38 file is missing.
    """
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    cells = {str(cell.get("cell_id")): dict(cell) for cell in payload.get("cells", [])}
    return cells, dict(payload.get("metadata", {}))


def load_scene_manifest(directory: Path) -> list[dict[str, object]]:
    """Load the Landsat download manifest.

    Parameters
    ----------
    directory : Path
        Directory containing ``download_manifest.json``.

    Returns
    -------
    list of dict
        Scene entries.

    Raises
    ------
    FileNotFoundError
        When the manifest is missing.
    """
    path = directory / "download_manifest.json"
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [dict(item) for item in payload]


def build_product(
    *,
    root: Path,
    landsat_dir: Path,
    heat_priority: Path,
    out_dir: Path,
    resolution: float = 30.0,
    cell_size: float = 400.0,
) -> dict[str, object]:
    """Build and write the heat-equity product.

    Parameters
    ----------
    root : Path
        P30 city dataset directory.
    landsat_dir : Path
        Landsat download directory.
    heat_priority : Path
        P38 heat-priority JSON.
    out_dir : Path
        Output directory.
    resolution : float
        LST cell size in metres.
    cell_size : float
        Analysis cell size in metres.

    Returns
    -------
    dict
        Product summary and written paths.
    """
    priority, p38_metadata = load_priority(heat_priority)
    bounds = tuple(float(value) for value in cast("list[float]", p38_metadata["bounds"]))
    crs = str(p38_metadata["crs"])
    shape = target_shape((bounds[0], bounds[1], bounds[2], bounds[3]), resolution)
    building = read_mask(root / "building_mask.tif", shape)
    water = read_mask(root / "water_mask.tif", shape)
    exclusion = building | water
    scenes = []
    scene_meta: list[dict[str, object]] = []
    for entry in load_scene_manifest(landsat_dir):
        files = entry.get("files")
        if not isinstance(files, dict):
            continue
        st_path = Path(str(files.get("lwir11", "")))
        qa_path = Path(str(files.get("qa_pixel", "")))
        if not st_path.exists() or not qa_path.exists():
            continue
        scene = read_landsat_lst(
            st_path,
            qa_path,
            bounds=(bounds[0], bounds[1], bounds[2], bounds[3]),
            crs=crs,
            resolution_m=resolution,
            exclusion_mask=exclusion,
            scene_id=str(entry.get("id", st_path.parent.name)),
        )
        scenes.append(scene)
        scene_meta.append(
            {
                "id": scene.scene_id,
                "datetime": entry.get("datetime"),
                "cloud_cover": entry.get("cloud_cover"),
                "valid_pixels": int(np.count_nonzero(scene.valid)),
            }
        )
    if not scenes:
        raise ValueError("no usable Landsat scenes were loaded")
    composite = composite_lst(scenes)
    cells = tuple(
        cell
        for cell in build_heat_equity_grid(
            composite,
            crs=crs,
            priority=priority,
            cell_size_m=cell_size,
        )
        if cell.cell_id in priority
    )
    metadata: dict[str, object] = {
        "dataset_id": "vancouver-city-2022",
        "cell_size_m": cell_size,
        "lst_resolution_m": resolution,
        "bounds": list(bounds),
        "crs": crs,
        "scene_dates": scene_meta,
        "lst_scale": LST_SCALE,
        "lst_offset_k": LST_OFFSET_K,
        "methods": {
            "lst": LST_EVIDENCE.to_dict(),
            "heat_equity": HEAT_EQUITY_EVIDENCE.to_dict(),
        },
        "caveats": [
            "LST is satellite surface temperature at the overpass, not air temperature "
            "or pedestrian thermal comfort.",
            "The heat-equity index is a relative screen, not a validated vulnerability "
            "model, health outcome model, or planting plan.",
            "Cloud, cloud shadow, water, and building rooftops are excluded; mixed "
            "pixels and emissivity remain sources of error.",
            "The four social indicators enter through the P38 equity score; LST is the "
            "fifth equal-weight component.",
        ],
    }
    paths = write_heat_equity_product(
        cells,
        out_dir,
        crs=crs,
        metadata=metadata,
        stem="heat_equity",
    )
    meta_path = out_dir / "heat_equity_meta.json"
    meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return {
        "cell_count": len(cells),
        "scene_count": len(scenes),
        "composite": composite.to_dict(),
        "high_tier_cells": sum(1 for cell in cells if cell.heat_equity_tier == "high"),
        "paths": {name: str(path) for name, path in paths.items()} | {"metadata": str(meta_path)},
    }


def main(argv: list[str] | None = None) -> int:
    """Run the Vancouver heat-equity build.

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
    out_dir = args.out or args.root
    result = build_product(
        root=args.root,
        landsat_dir=args.landsat_dir,
        heat_priority=args.heat_priority,
        out_dir=out_dir,
        resolution=args.resolution,
        cell_size=args.cell_size,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
