"""Street-level tree candidates from open imagery.

This module is deliberately separate from the LiDAR off-inventory layer. Street-level
detections are screening candidates with their own lineage, not replacements for official
inventory records or ALS-derived crowns.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import httpx
import numpy as np
from scipy.spatial import cKDTree

STREET_TREE_SCHEMA = "fresh-urban-forest.street-tree-candidates.v1"
STREET_TREE_METHOD = "open street-level imagery + semantic tree mask + metric depth"
KARTAVIEW_API = "https://api.kartaview.org/2.0/photo/"
KARTAVIEW_LICENSE = "CC BY-SA 4.0"
KARTAVIEW_ATTRIBUTION = "© Grab and KartaView contributors"
DEFAULT_HORIZONTAL_FOV_DEG = 60.0


@dataclass(frozen=True, slots=True)
class StreetImage:
    """A georeferenced street-level image.

    Attributes
    ----------
    provider : str
        Image provider identifier.
    image_id : str
        Provider image identifier.
    lon, lat : float
        Camera WGS84 position.
    heading_deg : float
        Compass heading of the camera centre, clockwise from north.
    width, height : int
        Pixel dimensions used for projection.
    captured_at : str
        Provider capture timestamp, or an empty string.
    image_url : str
        Image URL.
    license : str
        Provider licence.
    attribution : str
        Required attribution.
    horizontal_fov_deg : float
        Horizontal field of view. KartaView often omits this, so callers must record
        whether it is measured or assumed.
    fov_source : str
        ``provider`` or ``assumed``.
    pitch_deg : float
        Camera pitch; zero means the horizon is level.
    """

    provider: str
    image_id: str
    lon: float
    lat: float
    heading_deg: float
    width: int
    height: int
    captured_at: str
    image_url: str
    license: str
    attribution: str
    horizontal_fov_deg: float = DEFAULT_HORIZONTAL_FOV_DEG
    fov_source: str = "assumed"
    pitch_deg: float = 0.0


@dataclass(frozen=True, slots=True)
class StreetDetection:
    """One tree candidate projected from one image.

    Attributes
    ----------
    image_id : str
        Source image identifier.
    xmin, ymin, xmax, ymax : float
        Detection box in image pixels.
    score : float
        Screening score from zero to one.
    depth_m : float
        Metric camera-to-tree depth.
    lon, lat : float
        Projected candidate position.
    label : str
        Detector label.
    """

    image_id: str
    xmin: float
    ymin: float
    xmax: float
    ymax: float
    score: float
    depth_m: float
    lon: float
    lat: float
    label: str = "tree"


@dataclass(frozen=True, slots=True)
class StreetTreeCandidate:
    """A fused street-level tree candidate.

    Attributes
    ----------
    candidate_id : str
        Stable candidate identifier.
    lon, lat : float
        Fused WGS84 position.
    view_count : int
        Number of contributing image detections.
    score : float
        Maximum contributing score.
    uncertainty_m : float
        Positional uncertainty proxy in metres.
    image_ids : tuple of str
        Contributing image identifiers.
    source : str
        Fixed lineage marker.
    """

    candidate_id: str
    lon: float
    lat: float
    view_count: int
    score: float
    uncertainty_m: float
    image_ids: tuple[str, ...]
    source: str = "street_level_cv"


@dataclass(frozen=True, slots=True)
class MatchSummary:
    """Inventory matching counts for a candidate set.

    Attributes
    ----------
    candidate_count : int
        Number of candidates.
    matched_count : int
        Number matched to a public inventory record.
    tolerance_m : float
        Match radius.
    median_distance_m : float or None
        Median distance among matched candidates.
    """

    candidate_count: int
    matched_count: int
    tolerance_m: float
    median_distance_m: float | None


def bearing_offset_deg(pixel_x: float, width: int, horizontal_fov_deg: float) -> float:
    """Return the horizontal bearing offset for an image pixel.

    Parameters
    ----------
    pixel_x : float
        Pixel column.
    width : int
        Image width in pixels.
    horizontal_fov_deg : float
        Horizontal field of view.

    Returns
    -------
    float
        Offset in degrees, positive to the right of the camera centre.
    """
    if width <= 0:
        raise ValueError("width must be positive")
    if horizontal_fov_deg <= 0 or horizontal_fov_deg >= 179:
        raise ValueError("horizontal_fov_deg must be between 0 and 179")
    focal = (width / 2.0) / math.tan(math.radians(horizontal_fov_deg) / 2.0)
    return math.degrees(math.atan((pixel_x - width / 2.0) / focal))


def destination_lonlat(
    lon: float,
    lat: float,
    east_m: float,
    north_m: float,
) -> tuple[float, float]:
    """Move a WGS84 point by local east/north metres.

    Parameters
    ----------
    lon, lat : float
        Starting WGS84 position.
    east_m, north_m : float
        Local offsets in metres.

    Returns
    -------
    tuple of float
        Destination longitude and latitude.
    """
    latitude = lat + north_m / 110_540.0
    longitude = lon + east_m / (111_320.0 * max(math.cos(math.radians(lat)), 1e-6))
    return longitude, latitude


def ground_plane_range_m(
    image: StreetImage,
    pixel_y: float,
    *,
    camera_height_m: float = 2.5,
) -> float | None:
    """Estimate the horizontal ground range at a level-camera pixel.

    The camera is assumed level and the image centre is treated as the horizon. This is a
    sanity check, not a calibrated pose solution.

    Parameters
    ----------
    image : StreetImage
        Source image metadata.
    pixel_y : float
        Pixel row at the base of the detection box.
    camera_height_m : float
        Assumed camera height above the ground.

    Returns
    -------
    float or None
        Expected ground range in metres, or ``None`` above the horizon.
    """
    if camera_height_m <= 0:
        raise ValueError("camera_height_m must be positive")
    if image.width <= 0 or image.height <= 0:
        raise ValueError("image dimensions must be positive")
    focal = (image.width / 2.0) / math.tan(math.radians(image.horizontal_fov_deg) / 2.0)
    offset = pixel_y - image.height / 2.0
    if offset <= 0:
        return None
    angle = math.atan(offset / focal)
    if angle <= 0:
        return None
    return camera_height_m / math.tan(angle)


def ground_plane_ratio(
    image: StreetImage,
    pixel_y: float,
    depth_m: float,
    *,
    camera_height_m: float = 2.5,
) -> float | None:
    """Return observed depth divided by expected level-ground range.

    Parameters
    ----------
    image : StreetImage
        Source image metadata.
    pixel_y : float
        Pixel row at the base of the detection box.
    depth_m : float
        Observed metric depth.
    camera_height_m : float
        Assumed camera height above the ground.

    Returns
    -------
    float or None
        Depth/range ratio, or ``None`` above the horizon.
    """
    if depth_m <= 0:
        raise ValueError("depth_m must be positive")
    expected = ground_plane_range_m(
        image,
        pixel_y,
        camera_height_m=camera_height_m,
    )
    if expected is None:
        return None
    return depth_m / expected


def is_ground_plane_consistent(
    image: StreetImage,
    pixel_y: float,
    depth_m: float,
    *,
    camera_height_m: float = 2.5,
    min_ratio: float = 0.5,
    max_ratio: float = 2.0,
) -> bool:
    """Return whether depth is compatible with a level ground plane.

    Parameters
    ----------
    image : StreetImage
        Source image metadata.
    pixel_y : float
        Pixel row at the base of the detection box.
    depth_m : float
        Observed metric depth.
    camera_height_m : float
        Assumed camera height above the ground.
    min_ratio, max_ratio : float
        Accepted depth/range interval.

    Returns
    -------
    bool
        True when the ratio is inside the accepted interval.
    """
    if min_ratio <= 0 or max_ratio < min_ratio:
        raise ValueError("invalid ground-plane ratio bounds")
    ratio = ground_plane_ratio(
        image,
        pixel_y,
        depth_m,
        camera_height_m=camera_height_m,
    )
    return ratio is not None and min_ratio <= ratio <= max_ratio


def project_pixel(
    image: StreetImage,
    pixel_x: float,
    depth_m: float,
) -> tuple[float, float]:
    """Project a pixel and metric depth to WGS84 using a level pinhole camera.

    Parameters
    ----------
    image : StreetImage
        Source image metadata.
    pixel_x : float
        Pixel column of the tree base.
    depth_m : float
        Metric depth at the tree base.

    Returns
    -------
    tuple of float
        Candidate longitude and latitude.
    """
    if depth_m <= 0:
        raise ValueError("depth_m must be positive")
    offset = bearing_offset_deg(pixel_x, image.width, image.horizontal_fov_deg)
    bearing = math.radians(image.heading_deg + offset)
    ground_range = depth_m / max(math.cos(math.radians(offset)), 0.1)
    return destination_lonlat(
        image.lon,
        image.lat,
        ground_range * math.sin(bearing),
        ground_range * math.cos(bearing),
    )


def detection_from_box(
    image: StreetImage,
    box: tuple[float, float, float, float],
    *,
    score: float,
    depth_m: float,
    label: str = "tree",
) -> StreetDetection:
    """Create a projected detection from a source box.

    Parameters
    ----------
    image : StreetImage
        Source image metadata.
    box : tuple of float
        ``(xmin, ymin, xmax, ymax)`` box.
    score : float
        Screening score.
    depth_m : float
        Metric depth at the bottom centre of the box.
    label : str
        Detection label.

    Returns
    -------
    StreetDetection
        Projected detection.
    """
    xmin, ymin, xmax, ymax = box
    lon, lat = project_pixel(image, (xmin + xmax) / 2.0, depth_m)
    return StreetDetection(
        image_id=image.image_id,
        xmin=xmin,
        ymin=ymin,
        xmax=xmax,
        ymax=ymax,
        score=max(0.0, min(1.0, score)),
        depth_m=depth_m,
        lon=lon,
        lat=lat,
        label=label,
    )


def _local_xy(lon: float, lat: float, origin_lon: float, origin_lat: float) -> tuple[float, float]:
    """Return local east/north metres from an origin."""
    x = (lon - origin_lon) * 111_320.0 * math.cos(math.radians(origin_lat))
    y = (lat - origin_lat) * 110_540.0
    return x, y


def fuse_detections(
    detections: tuple[StreetDetection, ...],
    *,
    radius_m: float = 6.0,
    max_spread_m: float = 10.0,
) -> tuple[StreetTreeCandidate, ...]:
    """Fuse detections from multiple views into candidate positions.

    Joining is constrained by both the neighbour radius and the diameter of the
    resulting component. This prevents a sequence of nearby trees from collapsing
    into one long chain of detections.

    Parameters
    ----------
    detections : tuple of StreetDetection
        Projected detections.
    radius_m : float
        Maximum distance for joining detections.
    max_spread_m : float
        Maximum pairwise distance within one fused component.

    Returns
    -------
    tuple of StreetTreeCandidate
        Fused candidates, ordered by decreasing view count and score.
    """
    if not detections:
        return ()
    if radius_m <= 0:
        raise ValueError("radius_m must be positive")
    if max_spread_m <= 0:
        raise ValueError("max_spread_m must be positive")
    origin_lon, origin_lat = detections[0].lon, detections[0].lat
    points = [_local_xy(item.lon, item.lat, origin_lon, origin_lat) for item in detections]
    parent = list(range(len(detections)))
    members: dict[int, list[int]] = {index: [index] for index in range(len(detections))}

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    buckets: dict[tuple[int, int], list[int]] = {}
    for index, (east, north) in enumerate(points):
        key = (math.floor(east / radius_m), math.floor(north / radius_m))
        buckets.setdefault(key, []).append(index)

    edges: list[tuple[float, int, int]] = []
    for index, (east, north) in enumerate(points):
        col = math.floor(east / radius_m)
        row = math.floor(north / radius_m)
        for neighbour_col in range(col - 1, col + 2):
            for neighbour_row in range(row - 1, row + 2):
                for other in buckets.get((neighbour_col, neighbour_row), []):
                    if other >= index:
                        continue
                    other_east, other_north = points[other]
                    distance = math.hypot(east - other_east, north - other_north)
                    if distance <= radius_m:
                        edges.append((distance, index, other))
    edges.sort()

    for _distance, first, second in edges:
        root_first, root_second = find(first), find(second)
        if root_first == root_second:
            continue
        first_members = members[root_first]
        second_members = members[root_second]
        if any(
            math.hypot(
                points[first_index][0] - points[second_index][0],
                points[first_index][1] - points[second_index][1],
            )
            > max_spread_m
            for first_index in first_members
            for second_index in second_members
        ):
            continue
        parent[root_second] = root_first
        first_members.extend(second_members)
        del members[root_second]

    candidates: list[StreetTreeCandidate] = []
    for indices in members.values():
        selected = [detections[index] for index in indices]
        origin_lon = sum(item.lon for item in selected) / len(selected)
        origin_lat = sum(item.lat for item in selected) / len(selected)
        image_ids = tuple(sorted({item.image_id for item in selected}))
        spread = max(
            (
                math.hypot(*_local_xy(item.lon, item.lat, origin_lon, origin_lat))
                for item in selected
            ),
            default=0.0,
        )
        first_id = image_ids[0]
        candidates.append(
            StreetTreeCandidate(
                candidate_id=f"street:{first_id}:{len(candidates) + 1}",
                lon=origin_lon,
                lat=origin_lat,
                view_count=len(image_ids),
                score=max(item.score for item in selected),
                uncertainty_m=round(3.0 + spread, 3),
                image_ids=image_ids,
            )
        )
    candidates.sort(key=lambda item: (-item.view_count, -item.score, item.candidate_id))
    return tuple(candidates)


def match_inventory(
    candidates: tuple[StreetTreeCandidate, ...],
    inventory: tuple[tuple[float, float, str], ...],
    *,
    tolerance_m: float = 8.0,
) -> MatchSummary:
    """Match candidates to public tree records within a distance tolerance.

    The public inventory is incomplete for private trees, so the matched fraction is a
    descriptive statistic, not a precision estimate.

    Parameters
    ----------
    candidates : tuple of StreetTreeCandidate
        Street-level candidates.
    inventory : tuple of tuple
        ``(lon, lat, tree_id)`` records.
    tolerance_m : float
        Match radius in metres.

    Returns
    -------
    MatchSummary
        Match counts and median matched distance.
    """
    if tolerance_m <= 0:
        raise ValueError("tolerance_m must be positive")
    if not candidates or not inventory:
        return MatchSummary(
            candidate_count=len(candidates),
            matched_count=0,
            tolerance_m=tolerance_m,
            median_distance_m=None,
        )
    origin_lon, origin_lat = inventory[0][0], inventory[0][1]
    inventory_points = np.asarray(
        [_local_xy(lon, lat, origin_lon, origin_lat) for lon, lat, _tree_id in inventory],
        dtype=np.float64,
    )
    candidate_points = np.asarray(
        [_local_xy(item.lon, item.lat, origin_lon, origin_lat) for item in candidates],
        dtype=np.float64,
    )
    distances, _indices = cKDTree(inventory_points).query(candidate_points, k=1)
    matched = np.asarray(distances, dtype=np.float64)
    matched = matched[matched <= tolerance_m]
    median = None
    if matched.size:
        median = float(np.median(matched))
    return MatchSummary(
        candidate_count=len(candidates),
        matched_count=int(matched.size),
        tolerance_m=tolerance_m,
        median_distance_m=median,
    )


def candidates_geojson(
    candidates: tuple[StreetTreeCandidate, ...],
    *,
    method: str = STREET_TREE_METHOD,
) -> dict[str, object]:
    """Build a GeoJSON FeatureCollection for street-level candidates.

    Parameters
    ----------
    candidates : tuple of StreetTreeCandidate
        Fused candidates.
    method : str
        Method description stored on every feature.

    Returns
    -------
    dict
        GeoJSON FeatureCollection.
    """
    features: list[dict[str, object]] = []
    for candidate in candidates:
        features.append(
            {
                "type": "Feature",
                "id": candidate.candidate_id,
                "geometry": {
                    "type": "Point",
                    "coordinates": [candidate.lon, candidate.lat],
                },
                "properties": {
                    "candidate_id": candidate.candidate_id,
                    "source": candidate.source,
                    "method": method,
                    "view_count": candidate.view_count,
                    "score": round(candidate.score, 4),
                    "positional_uncertainty_m": candidate.uncertainty_m,
                    "image_ids": list(candidate.image_ids),
                    "not_ground_truth": True,
                    "lineage": (
                        "street-level imagery; separate from LiDAR off-inventory "
                        "and official inventory"
                    ),
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "name": "street_tree_candidates",
        "schema_version": STREET_TREE_SCHEMA,
        "features": features,
    }


def write_candidates(path: Path, candidates: tuple[StreetTreeCandidate, ...]) -> None:
    """Write candidate GeoJSON.

    Parameters
    ----------
    path : Path
        Output path.
    candidates : tuple of StreetTreeCandidate
        Fused candidates.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(candidates_geojson(candidates), indent=2) + "\n", encoding="utf-8")


class KartaViewClient:
    """Minimal public KartaView image client.

    The public endpoint does not require an access token. Images remain CC BY-SA 4.0 and
    must be attributed when redistributed.
    """

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=60.0, follow_redirects=True)

    def images_near(
        self,
        *,
        lon: float,
        lat: float,
        radius_m: int = 500,
        limit: int = 100,
    ) -> tuple[StreetImage, ...]:
        """Return nearby image metadata.

        Parameters
        ----------
        lon, lat : float
            Search centre.
        radius_m : int
            Search radius in metres.
        limit : int
            Maximum records to return.

        Returns
        -------
        tuple of StreetImage
            Parsed image metadata.
        """
        if radius_m <= 0 or limit <= 0:
            raise ValueError("radius_m and limit must be positive")
        response = self._client.get(
            KARTAVIEW_API,
            params={"lat": lat, "lng": lon, "radius": radius_m},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("KartaView response is not an object")
        result = payload.get("result")
        if not isinstance(result, dict):
            return ()
        records = result.get("data")
        if not isinstance(records, list):
            return ()
        images: list[StreetImage] = []
        for record in records[:limit]:
            if not isinstance(record, dict):
                continue
            try:
                image = _parse_kartaview_record(record)
            except (KeyError, TypeError, ValueError):
                continue
            if image is not None:
                images.append(image)
        return tuple(images)

    def image_bytes(self, image: StreetImage) -> bytes:
        """Download image bytes.

        Parameters
        ----------
        image : StreetImage
            Image metadata.

        Returns
        -------
        bytes
            Encoded image.
        """
        response = self._client.get(image.image_url)
        response.raise_for_status()
        return response.content


def _parse_kartaview_record(record: dict[str, object]) -> StreetImage | None:
    url = record.get("imageLthUrl")
    image_id = record.get("id")
    if not isinstance(url, str) or not url.startswith("https://"):
        return None
    if isinstance(image_id, (str, int)):
        identifier = str(image_id)
    else:
        return None
    width = _int_field(record, "width", 1280)
    height = _int_field(record, "height", 960)
    fov = _float_field(record, "fieldOfView", 0.0)
    fov_source = "provider" if fov > 0 else "assumed"
    return StreetImage(
        provider="kartaview",
        image_id=identifier,
        lon=_float_field(record, "lng"),
        lat=_float_field(record, "lat"),
        heading_deg=_float_field(record, "heading"),
        width=width,
        height=height,
        captured_at=str(record.get("dateAdded", "")),
        image_url=url,
        license=KARTAVIEW_LICENSE,
        attribution=KARTAVIEW_ATTRIBUTION,
        horizontal_fov_deg=fov if fov > 0 else DEFAULT_HORIZONTAL_FOV_DEG,
        fov_source=fov_source,
    )


def _float_field(record: dict[str, object], key: str, default: float | None = None) -> float:
    value = record.get(key, default)
    if value is None:
        raise ValueError(f"missing {key}")
    return float(cast("str | int | float", value))


def _int_field(record: dict[str, object], key: str, default: int) -> int:
    value = record.get(key, default)
    if value is None:
        return default
    return int(cast("str | int | float", value))
