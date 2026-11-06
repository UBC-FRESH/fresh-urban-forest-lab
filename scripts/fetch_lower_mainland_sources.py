#!/usr/bin/env python3
"""Fetch public source layers for the P34 Lower Mainland city instances."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PAGE_SIZE = 1000
USER_AGENT = "FRESH-Urban-Forest-Lab/0.3 public-data fetch"


def fetch_arcgis(  # pragma: no cover - operator I/O path
    layer_url: str,
    out_path: Path,
    *,
    where: str = "1=1",
    page_size: int = PAGE_SIZE,
) -> int:
    """Download all features from an ArcGIS REST layer as WGS84 GeoJSON.

    Parameters
    ----------
    layer_url : str
        Layer base URL, such as ``.../FeatureServer/0``.
    out_path : Path
        Destination GeoJSON.
    where : str
        SQL where clause.
    page_size : int
        Features per request.

    Returns
    -------
    int
        Number of downloaded features.
    """
    features: list[dict[str, Any]] = []
    offset = 0
    while True:
        params = {
            "where": where,
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
            "resultOffset": str(offset),
            "resultRecordCount": str(page_size),
            "orderByFields": "OBJECTID",
        }
        url = f"{layer_url}/query?{urlencode(params)}"
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=120) as response:
            payload = json.load(response)
        batch = payload.get("features", []) if isinstance(payload, dict) else []
        if not isinstance(batch, list):
            raise RuntimeError(f"unexpected ArcGIS response for {layer_url}")
        features.extend(feature for feature in batch if isinstance(feature, dict))
        print(f"{out_path.name}: {len(features)} features", flush=True)
        if len(batch) < page_size:
            break
        offset += len(batch)
        time.sleep(0.05)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")),
        encoding="utf-8",
    )
    return len(features)


def normalize_boundary(src: Path, dst: Path) -> int:  # pragma: no cover - operator I/O path
    """Keep the largest polygon from a boundary FeatureCollection.

    Parameters
    ----------
    src : Path
        Source GeoJSON.
    dst : Path
        Destination GeoJSON.

    Returns
    -------
    int
        Feature count written.
    """
    import geopandas as gpd

    frame = gpd.read_file(src)
    if frame.empty:
        raise RuntimeError(f"empty boundary: {src}")
    frame = frame.to_crs(3157)
    largest = frame.geometry.area.idxmax()
    selected = frame.loc[[largest]].to_crs(4326)
    selected["name"] = "city boundary"
    selected.to_file(dst, driver="GeoJSON")
    return len(selected)


def normalize_buildings(  # pragma: no cover - operator I/O path
    src: Path,
    dst: Path,
    *,
    height_field: str,
    id_field: str,
    name_field: str | None = None,
) -> int:
    """Normalise a building FeatureCollection for ``load_buildings``.

    Parameters
    ----------
    src : Path
        Source building GeoJSON.
    dst : Path
        Destination GeoJSON.
    height_field : str
        Source attribute containing building height.
    id_field : str
        Source attribute containing a stable identifier.
    name_field : str or None
        Optional source name field.

    Returns
    -------
    int
        Number of written building features.
    """
    import geopandas as gpd

    frame = gpd.read_file(src)
    if frame.empty:
        raise RuntimeError(f"empty building layer: {src}")
    frame = frame.to_crs(4326)
    output = gpd.GeoDataFrame(
        {
            "BLDG_UID": frame[id_field].astype(str),
            "height": frame[height_field].fillna(8.0).astype(float),
            "NAME": frame[name_field].fillna("").astype(str) if name_field else "",
        },
        geometry=frame.geometry,
        crs=4326,
    )
    output = output[output.geometry.notna() & ~output.geometry.is_empty]
    output.to_file(dst, driver="GeoJSON")
    return len(output)


def fetch_osm_roads(  # pragma: no cover - operator I/O path
    boundary_path: Path,
    out_path: Path,
) -> int:
    """Fetch major and residential OSM road centrelines for a boundary.

    Parameters
    ----------
    boundary_path : Path
        WGS84 boundary GeoJSON.
    out_path : Path
        Compressed GeoJSON output.

    Returns
    -------
    int
        Number of road features.
    """
    import gzip

    import geopandas as gpd

    frame = gpd.read_file(boundary_path).to_crs(4326)
    min_lon, min_lat, max_lon, max_lat = frame.total_bounds
    query = (
        f'[out:json][timeout:180];way["highway"]({min_lat},{min_lon},{max_lat},{max_lon});out geom;'
    )
    request = Request(
        "https://overpass-api.de/api/interpreter",
        data=urlencode({"data": query}).encode("utf-8"),
        headers={"User-Agent": USER_AGENT},
    )
    with urlopen(request, timeout=300) as response:
        payload = json.load(response)
    features: list[dict[str, Any]] = []
    for element in payload.get("elements", []):
        geometry = element.get("geometry")
        if not isinstance(geometry, list) or len(geometry) < 2:
            continue
        coords = [[float(point["lon"]), float(point["lat"])] for point in geometry]
        features.append(
            {
                "type": "Feature",
                "properties": {"highway": element.get("tags", {}).get("highway", "")},
                "geometry": {"type": "LineString", "coordinates": coords},
            }
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out_path, "wt", encoding="utf-8") as handle:
        json.dump(
            {"type": "FeatureCollection", "features": features},
            handle,
            separators=(",", ":"),
        )
    return len(features)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - operator I/O path
    """Fetch the P34 source set.

    Parameters
    ----------
    argv : list of str or None
        Command-line arguments.

    Returns
    -------
    int
        Process status.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/raw/lower_mainland"))
    parser.add_argument("--skip-roads", action="store_true")
    args = parser.parse_args(argv)
    root = args.root
    jobs = {
        "surrey/trees_raw.geojson": "https://services5.arcgis.com/YRpe0VKTJytZSSIB/arcgis/rest/services/SurreyTrees/FeatureServer/0",
        "surrey/buildings_raw.geojson": "https://services5.arcgis.com/YRpe0VKTJytZSSIB/arcgis/rest/services/Building%20Footprnts/FeatureServer/0",
        "surrey/boundary_raw.geojson": "https://services5.arcgis.com/YRpe0VKTJytZSSIB/arcgis/rest/services/Surrey%20City%20Boundaries/FeatureServer/0",
        "surrey/contours_raw.geojson": "https://services5.arcgis.com/YRpe0VKTJytZSSIB/arcgis/rest/services/contours%205m/FeatureServer/0",
        "burnaby/buildings_raw.geojson": "https://gis.burnaby.ca/arcgis/rest/services/OpenData/OpenData4/MapServer/18",
        "burnaby/boundary_raw.geojson": "https://gis.burnaby.ca/arcgis/rest/services/OpenData/OpenData3/MapServer/12",
        "coquitlam/buildings_raw.geojson": "https://services2.arcgis.com/Q6Lq3evZUGfPrN7o/arcgis/rest/services/Buildings_with_Zone_Category_and_Water_Pressure_Zone/FeatureServer/0",
        "coquitlam/boundary_raw.geojson": "https://services2.arcgis.com/Q6Lq3evZUGfPrN7o/arcgis/rest/services/City_Boundary/FeatureServer/33",
        "coquitlam/contours_raw.geojson": "https://services2.arcgis.com/Q6Lq3evZUGfPrN7o/arcgis/rest/services/Contours_2023/FeatureServer/0",
    }
    for relative, url in jobs.items():
        target = root / relative
        if target.exists() and target.stat().st_size > 0:
            print(f"skip existing {target}")
            continue
        fetch_arcgis(url, target)
    for city in ("surrey", "burnaby", "coquitlam"):
        normalize_boundary(
            root / city / "boundary_raw.geojson",
            root / city / "boundary.geojson",
        )
    normalize_buildings(
        root / "surrey" / "buildings_raw.geojson",
        root / "surrey" / "buildings.geojson",
        height_field="BUILDING_HEIGHT",
        id_field="FACILITYID",
        name_field="NAME",
    )
    normalize_buildings(
        root / "burnaby" / "buildings_raw.geojson",
        root / "burnaby" / "buildings.geojson",
        height_field="HEIGHT",
        id_field="OBJECTID",
        name_field="BUILDING_USE",
    )
    normalize_buildings(
        root / "coquitlam" / "buildings_raw.geojson",
        root / "coquitlam" / "buildings.geojson",
        height_field="HEIGHT",
        id_field="OBJECTID",
        name_field="GENERIC_NAME",
    )
    if not args.skip_roads:
        for city in ("surrey", "burnaby", "coquitlam"):
            slug = "burnaby_2022" if city == "burnaby" else f"{city}_2025"
            output = Path(f"data/processed/{slug}/roads.geojson.gz")
            count = fetch_osm_roads(root / city / "boundary.geojson", output)
            print(f"{city} roads: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
