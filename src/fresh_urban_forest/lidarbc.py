"""Discover LidarBC point-cloud and derived tiles by area of interest.

LidarBC publishes its open index as an ArcGIS feature service. The point-cloud layer
(layer 4) carries the S3 download URL, acquisition year, projection, and density. The
derived DSM/DEM layers carry the same download fields, so the helper takes a layer id.
"""

from __future__ import annotations

from collections.abc import Mapping

import httpx

from fresh_urban_forest.tiles import LidarTile

LIDARBC_SERVICE_URL = (
    "https://services6.arcgis.com/ubm4tcTYICKBpist/arcgis/rest/services/"
    "LiDAR_BC_S3_Public/FeatureServer"
)
LIDARBC_POINT_CLOUD_LAYER = 4
LIDARBC_DSM_LAYERS: tuple[int, ...] = (1, 2, 3)
LIDARBC_DEM_LAYERS: tuple[int, ...] = (5, 6)
LIDARBC_PAGE_SIZE = 1000


def discover_lidarbc_tiles(
    bbox_wgs84: tuple[float, float, float, float],
    *,
    layer_id: int = LIDARBC_POINT_CLOUD_LAYER,
    page_size: int = LIDARBC_PAGE_SIZE,
    timeout_sec: float = 60.0,
    client: httpx.Client | None = None,
    service_url: str = LIDARBC_SERVICE_URL,
) -> tuple[LidarTile, ...]:
    """Query the LidarBC index for tiles intersecting a WGS84 bounding box.

    Parameters
    ----------
    bbox_wgs84 : tuple of float
        ``(min_lon, min_lat, max_lon, max_lat)``.
    layer_id : int
        ArcGIS layer id. The default is the classified point-cloud index.
    page_size : int
        Number of records per request. The service caps this at its max record count.
    timeout_sec : float
        Per-request timeout in seconds.
    client : httpx.Client or None
        Optional injected client for tests.
    service_url : str
        Override for the ArcGIS FeatureServer root.

    Returns
    -------
    tuple of LidarTile
        Tiles intersecting the bounding box, ordered by the service.
    """
    validate_bbox(bbox_wgs84)
    owned_client = client is None
    active_client = client or httpx.Client(follow_redirects=True, timeout=timeout_sec)
    url = f"{service_url.rstrip('/')}/{layer_id}/query"
    tiles: list[LidarTile] = []
    offset = 0
    try:
        while True:
            params = {
                "where": "1=1",
                "outFields": "*",
                "returnGeometry": "true",
                "f": "geojson",
                "geometry": ",".join(str(value) for value in bbox_wgs84),
                "geometryType": "esriGeometryEnvelope",
                "inSR": "4326",
                "outSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
                "resultOffset": str(offset),
                "resultRecordCount": str(page_size),
                "orderByFields": "OBJECTID",
            }
            response = active_client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
            features = payload.get("features", []) if isinstance(payload, Mapping) else []
            if not isinstance(features, list):
                break
            for feature in features:
                if not isinstance(feature, Mapping):
                    continue
                tile = _tile_from_feature(feature, layer_id)
                if tile is not None:
                    tiles.append(tile)
            if len(features) < page_size:
                break
            offset += page_size
    finally:
        if owned_client:
            active_client.close()
    return tuple(tiles)


def validate_bbox(bbox: tuple[float, float, float, float]) -> None:
    """Validate a WGS84 bounding box.

    Parameters
    ----------
    bbox : tuple of float
        ``(min_lon, min_lat, max_lon, max_lat)``.

    Raises
    ------
    ValueError
        When the box is reversed or outside valid longitude/latitude ranges.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    if not (-180 <= min_lon < max_lon <= 180):
        raise ValueError("longitude bounds must satisfy -180 <= min_lon < max_lon <= 180")
    if not (-90 <= min_lat < max_lat <= 90):
        raise ValueError("latitude bounds must satisfy -90 <= min_lat < max_lat <= 90")


def _tile_from_feature(feature: Mapping[str, object], layer_id: int) -> LidarTile | None:
    """Convert one ArcGIS GeoJSON feature to a tile.

    Parameters
    ----------
    feature : mapping
        GeoJSON feature.
    layer_id : int
        Source layer id, recorded in the notes.

    Returns
    -------
    LidarTile or None
        The tile, or ``None`` when the feature has no download URL.
    """
    properties = feature.get("properties", {})
    if not isinstance(properties, Mapping):
        return None
    url = _text(properties.get("s3Url"))
    if not url:
        return None
    filename = _text(properties.get("filename")) or url.rsplit("/", 1)[-1]
    tile_id = _text(properties.get("maptile")) or _text(properties.get("OBJECTID")) or filename
    bbox = _feature_bbox(feature)
    return LidarTile(
        source="lidarbc",
        tile_id=tile_id,
        filename=filename,
        url=url,
        year=_int_or_none(properties.get("year")),
        projection=_text(properties.get("projection")),
        density=_float_or_none(properties.get("density")),
        bbox=bbox,
        metadata_url=_text(properties.get("s3RptUrl")),
        notes=(
            f"LidarBC layer {layer_id}; project {_text(properties.get('oper_name')) or 'unknown'}; "
            f"classes {_text(properties.get('classes')) or 'not listed'}."
        ),
    )


def _feature_bbox(feature: Mapping[str, object]) -> tuple[float, float, float, float]:
    """Extract a WGS84 bounding box from a GeoJSON geometry.

    Parameters
    ----------
    feature : mapping
        GeoJSON feature.

    Returns
    -------
    tuple of float
        ``(min_lon, min_lat, max_lon, max_lat)``, or zeros when no geometry is present.
    """
    geometry = feature.get("geometry", {})
    if not isinstance(geometry, Mapping):
        return (0.0, 0.0, 0.0, 0.0)
    raw = geometry.get("coordinates", [])
    points: list[tuple[float, float]] = []
    _collect_points(raw, points)
    if not points:
        return (0.0, 0.0, 0.0, 0.0)
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
        Output list that receives ``(lon, lat)`` pairs.
    """
    if not isinstance(value, (list, tuple)):
        return
    if len(value) >= 2 and all(isinstance(item, (int, float)) for item in value[:2]):
        points.append((float(value[0]), float(value[1])))
        return
    for item in value:
        _collect_points(item, points)


def _text(value: object) -> str:
    """Return a stripped string or an empty string.

    Parameters
    ----------
    value : object
        Candidate value.

    Returns
    -------
    str
        The cleaned string.
    """
    if value is None:
        return ""
    return str(value).strip()


def _int_or_none(value: object) -> int | None:
    """Convert an optional value to an integer.

    Parameters
    ----------
    value : object
        Candidate value.

    Returns
    -------
    int or None
        The integer, or ``None`` when invalid.
    """
    if value is None or value == "":
        return None
    try:
        return int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _float_or_none(value: object) -> float | None:
    """Convert an optional value to a float.

    Parameters
    ----------
    value : object
        Candidate value.

    Returns
    -------
    float or None
        The float, or ``None`` when invalid.
    """
    if value is None or value == "":
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
