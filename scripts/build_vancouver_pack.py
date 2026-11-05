#!/usr/bin/env python3
"""Assemble the portable Vancouver city dataset for the existing web app."""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
from pathlib import Path

import geopandas as gpd

from fresh_urban_forest.city_pack import build_city_pack
from fresh_urban_forest.models import SourceRecord, tree_from_dict
from fresh_urban_forest.terrain import read_raster


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
        "--aoi",
        type=Path,
        default=Path("data/raw/vancouver/local_area_boundary.geojson"),
    )
    parser.add_argument(
        "--buildings",
        type=Path,
        default=Path("data/raw/vancouver/building_footprints.geojson"),
    )
    parser.add_argument("--max-trees", type=int, default=30_000)
    parser.add_argument("--max-buildings", type=int, default=12_000)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the pack build.

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
    root = args.root
    with gzip.open(root / "trees.json.gz", "rt", encoding="utf-8") as handle:
        trees = tuple(tree_from_dict(item) for item in json.load(handle))
    city_metrics = json.loads((root / "city_metrics.json").read_text(encoding="utf-8"))
    inventory_summary = json.loads((root / "inventory_summary.json").read_text(encoding="utf-8"))
    dem = read_raster(root / "dem.tif")
    chm = read_raster(root / "chm.tif")
    building_height = read_raster(root / "building_height.tif")
    boundary = _boundary(args.aoi)
    generated = dt.datetime.now(dt.UTC).isoformat()
    sources = _sources(generated)
    dataset = build_city_pack(
        trees=trees,
        city_metrics=city_metrics,
        inventory_summary=inventory_summary,
        dem=dem,
        chm=chm,
        building_footprints=args.buildings,
        building_height=building_height,
        boundary=boundary,
        sources=sources,
        out_dir=root,
        max_trees=args.max_trees,
        max_buildings=args.max_buildings,
        generated_utc=generated,
    )
    print(
        f"wrote {root}; visual trees {len(dataset.trees)}, "
        f"buildings {len(dataset.buildings)}, "
        f"terrain {dataset.terrain.width}x{dataset.terrain.height}"
    )
    return 0


def _boundary(path: Path) -> tuple[tuple[float, float], ...]:
    """Return the largest local-area union ring in WGS84."""
    areas = gpd.read_file(path).to_crs(3157)
    union = areas.geometry.union_all()
    if union.geom_type == "MultiPolygon":
        union = max(union.geoms, key=lambda polygon: polygon.area)
    to_wgs84 = gpd.GeoSeries([union], crs=3157).to_crs(4326).iloc[0]
    return tuple((float(x), float(y)) for x, y in list(to_wgs84.exterior.coords))


def _sources(generated: str) -> tuple[SourceRecord, ...]:
    """Return provenance records for the city pack."""
    return (
        SourceRecord(
            source_id="vancouver_lidar_2022",
            title="City of Vancouver LiDAR 2022",
            publisher="City of Vancouver",
            url="https://opendata.vancouver.ca/explore/dataset/lidar-2022/",
            licence="Open Government Licence - Vancouver",
            access_mode="direct_http",
            retrieved_utc=generated,
            notes="181 classified tiles, EPSG:3157, CGVD28GVRD, ~49 points/m².",
        ),
        SourceRecord(
            source_id="vancouver_public_trees",
            title="City of Vancouver public trees",
            publisher="City of Vancouver",
            url="https://opendata.vancouver.ca/explore/dataset/public-trees/",
            licence="Open Government Licence - Vancouver",
            access_mode="direct_http",
            retrieved_utc=generated,
            notes="184,152 mapped public trees; private trees are excluded.",
        ),
        SourceRecord(
            source_id="vancouver_local_areas",
            title="City of Vancouver local-area boundary",
            publisher="City of Vancouver",
            url="https://opendata.vancouver.ca/explore/dataset/local-area-boundary/",
            licence="Open Government Licence - Vancouver",
            access_mode="direct_http",
            retrieved_utc=generated,
            notes="22 local-area polygons; the union is the city AOI.",
        ),
        SourceRecord(
            source_id="vancouver_buildings_2015",
            title="City of Vancouver building footprints 2015",
            publisher="City of Vancouver",
            url="https://opendata.vancouver.ca/explore/dataset/building-footprints-2015/",
            licence="Open Government Licence - Vancouver",
            access_mode="direct_http",
            retrieved_utc=generated,
            notes="154,124 approximate footprints; heights sampled from the 2022 LiDAR.",
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
