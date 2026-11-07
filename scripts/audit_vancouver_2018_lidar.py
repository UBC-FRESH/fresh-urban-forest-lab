#!/usr/bin/env python3
"""Build and audit the full City of Vancouver 2018 LiDAR tile manifest.

The Open Data portal exposes 181 tile polygons and ZIP links. This operator tool
records the full index, compares it with the city boundary, and reports which tiles
are already present. It does not bypass Cloudflare or download the full multi-gigabyte
collection.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast
from urllib.parse import urlencode
from urllib.request import urlopen

import geopandas as gpd

API = "https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/lidar-2018/records"
PORTAL = "https://opendata.vancouver.ca/explore/dataset/lidar-2018/"
DEFAULT_BOUNDARY = Path("data/processed/vancouver_2022/boundary.geojson")
DEFAULT_EXISTING = Path("data/raw/city_lidar/2018")
DEFAULT_OUT = Path("data/raw/tiles/vancouver_2018_city.json")


def _bbox(geometry: Mapping[str, object]) -> tuple[float, float, float, float]:
    """Return a WGS84 bounding box from a GeoJSON polygon."""
    coordinates = cast("list[list[list[float]]]", geometry["coordinates"])
    points = [point for ring in coordinates for point in ring]
    if not points:
        raise ValueError("tile geometry has no coordinates")
    longitudes = [float(point[0]) for point in points]
    latitudes = [float(point[1]) for point in points]
    return (min(longitudes), min(latitudes), max(longitudes), max(latitudes))


def parse_record(record: Mapping[str, object]) -> dict[str, object]:
    """Convert one Open Data record to a normalized tile record.

    Parameters
    ----------
    record : mapping
        Record from the City LiDAR 2018 API.

    Returns
    -------
    dict
        Normalized tile with id, filename, URL, bbox, and metadata.

    Raises
    ------
    ValueError
        When the record is missing an id, URL, or polygon.
    """
    name = str(record.get("name", "")).strip()
    url = str(record.get("lidar_url", "")).strip()
    geom = record.get("geom")
    if not name or not url or not isinstance(geom, Mapping):
        raise ValueError("tile record is missing name, URL, or geometry")
    geometry = geom.get("geometry")
    if not isinstance(geometry, Mapping):
        raise ValueError("tile record has no geometry")
    return {
        "source": "vancouver-lidar-2018",
        "tile_id": name,
        "filename": f"{name}.zip",
        "url": url,
        "year": 2018,
        "projection": "utm10",
        "density": 30.0,
        "bbox": list(_bbox(geometry)),
        "metadata_url": PORTAL,
        "notes": (
            "City of Vancouver 2018 LiDAR. ZIP contains LAS and PRJ; "
            "webtransfer may block automated HTTP clients."
        ),
    }


def build_manifest(
    records: Sequence[Mapping[str, object]],
    *,
    generated_utc: str | None = None,
) -> dict[str, object]:
    """Build a normalized full-city tile manifest.

    Parameters
    ----------
    records : sequence of mapping
        Open Data records.
    generated_utc : str or None
        Override timestamp for tests.

    Returns
    -------
    dict
        Manifest with a tile list.
    """
    tiles = [parse_record(record) for record in records]
    tiles.sort(key=lambda tile: str(tile["tile_id"]))
    return {
        "schema_version": "fresh-urban-forest.lidar-index.v1",
        "source": "vancouver-lidar-2018",
        "generated_utc": generated_utc or dt.datetime.now(dt.UTC).isoformat(),
        "tile_count": len(tiles),
        "tiles": tiles,
    }


def _tile_feature(tile: Mapping[str, object]) -> dict[str, object]:
    """Build a rectangular GeoJSON feature from a tile bbox."""
    bbox = cast("list[float]", tile["bbox"])
    return {
        "type": "Feature",
        "properties": {"tile_id": tile["tile_id"], "filename": tile["filename"]},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [bbox[0], bbox[1]],
                    [bbox[0], bbox[3]],
                    [bbox[2], bbox[3]],
                    [bbox[2], bbox[1]],
                    [bbox[0], bbox[1]],
                ]
            ],
        },
    }


def coverage_audit(
    manifest: Mapping[str, object],
    *,
    boundary_path: Path,
    existing_dir: Path,
) -> dict[str, object]:
    """Compare the full tile index with the city boundary and existing files.

    Parameters
    ----------
    manifest : mapping
        Output of :func:`build_manifest`.
    boundary_path : Path
        City boundary GeoJSON.
    existing_dir : Path
        Directory containing downloaded 2018 tiles.

    Returns
    -------
    dict
        Coverage and missing-tile audit.

    Raises
    ------
    FileNotFoundError
        When the boundary file is absent.
    """
    if not boundary_path.exists():
        raise FileNotFoundError(boundary_path)
    boundary = gpd.read_file(boundary_path)
    if boundary.crs is None:
        boundary = boundary.set_crs("EPSG:4326")
    tiles = gpd.GeoDataFrame.from_features(
        [_tile_feature(tile) for tile in cast("list[Mapping[str, object]]", manifest["tiles"])],
        crs="EPSG:4326",
    )
    boundary_projected = boundary.to_crs("EPSG:3157")
    tiles_projected = tiles.to_crs("EPSG:3157")
    boundary_union = boundary_projected.geometry.union_all()
    tile_union = tiles_projected.geometry.union_all()
    covered = float(tile_union.intersection(boundary_union).area / 1_000_000.0)
    boundary_area = float(boundary_union.area / 1_000_000.0)
    existing_names = (
        {path.name for path in existing_dir.glob("*") if path.suffix.lower() in {".las", ".zip"}}
        if existing_dir.exists()
        else set()
    )
    present = [
        tile
        for tile in cast("list[Mapping[str, object]]", manifest["tiles"])
        if str(tile["filename"]) in existing_names
        or str(tile["filename"]).replace(".zip", ".las") in existing_names
    ]
    present_ids = {str(tile["tile_id"]) for tile in present}
    present_geometries = tiles_projected[tiles["tile_id"].isin(present_ids)]
    present_union = present_geometries.geometry.union_all()
    present_area = (
        float(present_union.intersection(boundary_union).area / 1_000_000.0)
        if not present_geometries.empty
        else 0.0
    )
    missing = [
        str(tile["tile_id"])
        for tile in cast("list[Mapping[str, object]]", manifest["tiles"])
        if str(tile["tile_id"]) not in present_ids
    ]
    return {
        "tile_count": len(cast("list[Mapping[str, object]]", manifest["tiles"])),
        "boundary_area_km2": round(boundary_area, 3),
        "tile_coverage_km2": round(covered, 3),
        "coverage_fraction": round(covered / boundary_area, 4) if boundary_area else 0.0,
        "downloaded_tile_count": len(present_ids),
        "downloaded_coverage_km2": round(present_area, 3),
        "missing_tile_count": len(missing),
        "missing_tiles": missing,
        "download_blocker": (
            "The full collection is ~181 ZIP tiles and may be tens of gigabytes. "
            "webtransfer.vancouver.ca returns HTTP 403 to plain HTTP clients; use the "
            "existing headed-browser downloader with an explicit operator decision."
        ),
    }


def fetch_records(  # pragma: no cover - network operator path
    page_size: int = 100,
) -> list[dict[str, object]]:
    """Fetch every 2018 LiDAR record from the public Open Data API.

    Parameters
    ----------
    page_size : int
        Records requested per page.

    Returns
    -------
    list of dict
        Raw Open Data records.
    """
    records: list[dict[str, object]] = []
    offset = 0
    while True:
        query = urlencode({"limit": page_size, "offset": offset})
        with urlopen(f"{API}?{query}", timeout=60) as response:
            payload = json.load(response)
        page = payload.get("results", [])
        records.extend(record for record in page if isinstance(record, dict))
        if len(page) < page_size:
            break
        offset += page_size
    return records


def main(argv: Sequence[str] | None = None) -> int:
    """Run the manifest build and coverage audit.

    Parameters
    ----------
    argv : sequence of str or None
        Arguments.

    Returns
    -------
    int
        Zero on success.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--boundary", type=Path, default=DEFAULT_BOUNDARY)
    parser.add_argument("--existing", type=Path, default=DEFAULT_EXISTING)
    parser.add_argument("--records", type=Path, help="Read saved Open Data records")
    args = parser.parse_args(argv)
    if args.records is not None:
        records = json.loads(args.records.read_text(encoding="utf-8"))
    else:
        records = fetch_records()
    manifest = build_manifest(records)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    audit = coverage_audit(manifest, boundary_path=args.boundary, existing_dir=args.existing)
    print(json.dumps({"manifest": str(args.out), "audit": audit}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
