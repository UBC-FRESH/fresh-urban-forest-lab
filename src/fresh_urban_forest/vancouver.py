"""Discover City of Vancouver LiDAR tiles by year and area of interest.

The City publishes a tabular tile index through its Opendatasoft API. Each record has a
tile name, a direct ZIP URL on ``webtransfer.vancouver.ca``, and a polygon geometry. The
download host may block automated clients, so discovery and materialization are separated:
the manifest is still useful for a browser-assisted or manual fetch.
"""

from __future__ import annotations

from collections.abc import Mapping

import httpx

from fresh_urban_forest.tiles import LidarTile

VANCOUVER_API_BASE = "https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets"
VANCOUVER_LIDAR_YEARS: tuple[int, ...] = (2013, 2018, 2022)
VANCOUVER_DENSITY: dict[int, float] = {2013: 12.0, 2018: 30.0, 2022: 49.0}
VANCOUVER_PAGE_SIZE = 100


def discover_vancouver_tiles(
    year: int,
    bbox_wgs84: tuple[float, float, float, float],
    *,
    page_size: int = VANCOUVER_PAGE_SIZE,
    timeout_sec: float = 60.0,
    client: httpx.Client | None = None,
    api_base: str = VANCOUVER_API_BASE,
) -> tuple[LidarTile, ...]:
    """Query the City of Vancouver tile index for one LiDAR year.

    Parameters
    ----------
    year : int
        One of 2013, 2018, or 2022.
    bbox_wgs84 : tuple of float
        ``(min_lon, min_lat, max_lon, max_lat)``.
    page_size : int
        Records per request.
    timeout_sec : float
        Per-request timeout.
    client : httpx.Client or None
        Optional injected client.
    api_base : str
        Override for the Opendatasoft API root.

    Returns
    -------
    tuple of LidarTile
        Tiles intersecting the bounding box.

    Raises
    ------
    ValueError
        When the year is not supported.
    """
    if year not in VANCOUVER_LIDAR_YEARS:
        raise ValueError(f"unsupported Vancouver LiDAR year: {year}")
    owned_client = client is None
    active_client = client or httpx.Client(follow_redirects=True, timeout=timeout_sec)
    url = f"{api_base.rstrip('/')}/lidar-{year}/records"
    tiles: list[LidarTile] = []
    offset = 0
    try:
        while True:
            response = active_client.get(
                url,
                params={"limit": page_size, "offset": offset},
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, Mapping):
                break
            records = payload.get("results", [])
            if not isinstance(records, list) or not records:
                break
            for record in records:
                if not isinstance(record, Mapping):
                    continue
                tile = _tile_from_record(record, year)
                if tile is not None and _intersects(tile.bbox, bbox_wgs84):
                    tiles.append(tile)
            total = (
                int(payload.get("total_count", 0))
                if isinstance(payload.get("total_count"), (int, str))
                else 0
            )
            offset += len(records)
            if offset >= total or len(records) < page_size:
                break
    finally:
        if owned_client:
            active_client.close()
    return tuple(tiles)


def _tile_from_record(record: Mapping[str, object], year: int) -> LidarTile | None:
    """Convert one API record to a tile.

    Parameters
    ----------
    record : mapping
        API record.
    year : int
        LiDAR year.

    Returns
    -------
    LidarTile or None
        The tile, or ``None`` when the record lacks a URL or geometry.
    """
    name = str(record.get("name", "")).strip()
    url = str(record.get("lidar_url", "")).strip()
    if not name or not url:
        return None
    bbox = _record_bbox(record)
    if bbox is None:
        return None
    return LidarTile(
        source=f"vancouver-lidar-{year}",
        tile_id=name,
        filename=f"{name}.zip",
        url=url,
        year=year,
        projection="utm10",
        density=VANCOUVER_DENSITY.get(year),
        bbox=bbox,
        metadata_url=f"https://opendata.vancouver.ca/explore/dataset/lidar-{year}/",
        notes=(
            "City of Vancouver LiDAR tile. The webtransfer host may block automated "
            "downloads; use the manifest for a browser-assisted or manual fetch."
        ),
    )


def _record_bbox(record: Mapping[str, object]) -> tuple[float, float, float, float] | None:
    """Extract a WGS84 bounding box from an API record.

    Parameters
    ----------
    record : mapping
        API record.

    Returns
    -------
    tuple of float or None
        ``(min_lon, min_lat, max_lon, max_lat)``, or ``None`` when no polygon is present.
    """
    geom = record.get("geom")
    if not isinstance(geom, Mapping):
        return None
    geometry = geom.get("geometry")
    if not isinstance(geometry, Mapping):
        return None
    coordinates = geometry.get("coordinates", [])
    points: list[tuple[float, float]] = []
    _collect_points(coordinates, points)
    if not points:
        return None
    lons = [point[0] for point in points]
    lats = [point[1] for point in points]
    return (min(lons), min(lats), max(lons), max(lats))


def _collect_points(value: object, points: list[tuple[float, float]]) -> None:
    """Recursively collect coordinate pairs from GeoJSON coordinates.

    Parameters
    ----------
    value : object
        Nested coordinate list.
    points : list of tuple of float
        Output list.
    """
    if not isinstance(value, (list, tuple)):
        return
    if len(value) >= 2 and all(isinstance(item, (int, float)) for item in value[:2]):
        points.append((float(value[0]), float(value[1])))
        return
    for item in value:
        _collect_points(item, points)


def _intersects(
    first: tuple[float, float, float, float], second: tuple[float, float, float, float]
) -> bool:
    """Test whether two WGS84 bounding boxes intersect.

    Parameters
    ----------
    first : tuple of float
        First bounding box.
    second : tuple of float
        Second bounding box.

    Returns
    -------
    bool
        ``True`` when the boxes overlap.
    """
    return not (
        first[2] < second[0] or first[0] > second[2] or first[3] < second[1] or first[1] > second[3]
    )
