#!/usr/bin/env python3
"""Build deterministic candidate planting sites from P39 gap components.

The build joins P42/P44 action labels as context only. It does not model ownership,
access, utilities, soil, irrigation, or field conditions, and the output is not a
planting plan.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from build_vancouver_planting_opportunity import load_rasters, load_roads, road_masks
from fresh_urban_forest.planting_opportunity import build_gap_masks
from fresh_urban_forest.site_scenario import (
    CANDIDATE_EVIDENCE,
    DEFAULT_CELL_SIZE_M,
    DEFAULT_MAX_CANDIDATE_SITES,
    DEFAULT_MAX_SITES_PER_CELL,
    DEFAULT_SITE_MIN_AREA_M2,
    SITE_CANDIDATES_SCHEMA_VERSION,
    extract_candidate_sites,
    write_candidate_site_product,
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
        help="City dataset directory with DEM, CHM, masks, and roads",
    )
    parser.add_argument(
        "--action",
        type=Path,
        default=None,
        help="P42/P44 canopy-action JSON; defaults to <root>/canopy_action.json",
    )
    parser.add_argument("--out", type=Path, default=None, help="Output directory")
    parser.add_argument("--resolution", type=float, default=5.0, help="Raster cell size")
    parser.add_argument(
        "--cell-size", type=float, default=DEFAULT_CELL_SIZE_M, help="Analysis cell size"
    )
    parser.add_argument(
        "--site-min-area",
        type=float,
        default=DEFAULT_SITE_MIN_AREA_M2,
        help="Minimum contiguous component area in square metres",
    )
    parser.add_argument(
        "--max-sites",
        type=int,
        default=DEFAULT_MAX_CANDIDATE_SITES,
        help="Global candidate cap",
    )
    parser.add_argument(
        "--max-sites-per-cell",
        type=int,
        default=DEFAULT_MAX_SITES_PER_CELL,
        help="Per-cell candidate cap",
    )
    return parser.parse_args(argv)


def load_action_cells(path: Path) -> dict[str, dict[str, object]]:
    """Load P42/P44 action cells keyed by cell id.

    Parameters
    ----------
    path : Path
        Canopy-action JSON.

    Returns
    -------
    dict
        Cell id to action properties.

    Raises
    ------
    FileNotFoundError
        When the action file is missing.
    """
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(cell.get("cell_id")): dict(cell) for cell in payload.get("cells", [])}


def build_product(
    *,
    root: Path,
    action: Path | None,
    out_dir: Path,
    resolution: float = 5.0,
    cell_size: float = DEFAULT_CELL_SIZE_M,
    site_min_area: float = DEFAULT_SITE_MIN_AREA_M2,
    max_sites: int = DEFAULT_MAX_CANDIDATE_SITES,
    max_sites_per_cell: int = DEFAULT_MAX_SITES_PER_CELL,
) -> dict[str, object]:
    """Build and write the candidate-site product.

    Parameters
    ----------
    root : Path
        City dataset directory.
    action : Path or None
        Canopy-action JSON; defaults to ``root / "canopy_action.json"``.
    out_dir : Path
        Output directory.
    resolution : float
        Raster cell size in metres.
    cell_size : float
        Analysis cell size in metres.
    site_min_area : float
        Minimum component area in square metres.
    max_sites : int
        Global candidate cap.
    max_sites_per_cell : int
        Per-cell candidate cap.

    Returns
    -------
    dict
        Summary and written paths.

    Raises
    ------
    ValueError
        When the action product has no cells.
    """
    dem, canopy, building, water, bounds, crs = load_rasters(root, resolution)
    roads = load_roads(root / "roads.geojson.gz", crs)
    surface, centre = road_masks(roads, bounds=bounds, shape=dem.shape)
    masks = build_gap_masks(
        dem=dem,
        canopy_height=canopy,
        building_mask=building,
        water_mask=water,
        road_surface_mask=surface,
        road_center_mask=centre,
        cell_size_m=resolution,
    )
    action_path = action or (root / "canopy_action.json")
    action_cells = load_action_cells(action_path)
    if not action_cells:
        raise ValueError("canopy-action product has no cells")
    sites = extract_candidate_sites(
        masks,
        bounds=bounds,
        crs=crs,
        action_cells=action_cells,
        site_min_area_m2=site_min_area,
        cell_size_m=cell_size,
        max_sites=max_sites,
        max_sites_per_cell=max_sites_per_cell,
    )
    action_counts = Counter(site.action_class for site in sites)
    metadata: dict[str, object] = {
        "schema_version": SITE_CANDIDATES_SCHEMA_VERSION,
        "dataset_id": "vancouver-city-2022",
        "cell_size_m": cell_size,
        "raster_resolution_m": resolution,
        "bounds": list(bounds),
        "crs": crs,
        "thresholds": {
            "site_min_area_m2": site_min_area,
            "max_sites": max_sites,
            "max_sites_per_cell": max_sites_per_cell,
        },
        "candidate_count": len(sites),
        "action_counts": dict(sorted(action_counts.items())),
        "methods": {"candidate": CANDIDATE_EVIDENCE.to_dict()},
        "caveats": [
            "Candidate sites are contiguous open-ground components, not parcels.",
            "Ownership, access, utilities, soil, irrigation, maintenance, and cost are "
            "not modelled.",
            "P42/P44 action labels are joined as context only; they are not planting permits.",
            "The candidate layer is not a planting plan or field-validated recommendation.",
        ],
    }
    paths = write_candidate_site_product(sites, out_dir, metadata=metadata)
    return {
        "candidate_count": len(sites),
        "action_counts": dict(sorted(action_counts.items())),
        "paths": {name: str(path) for name, path in paths.items()},
    }


def main(argv: list[str] | None = None) -> int:
    """Run the Vancouver candidate-site build.

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
        action=args.action,
        out_dir=out_dir,
        resolution=args.resolution,
        cell_size=args.cell_size,
        site_min_area=args.site_min_area,
        max_sites=args.max_sites,
        max_sites_per_cell=args.max_sites_per_cell,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
