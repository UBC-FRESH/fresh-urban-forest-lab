"""Load and normalise public tree inventories and campus context layers.

UBC publishes a GeoJSON snapshot through its geospatial open-data repository. The City of
Vancouver publishes a daily CSV export. The two schemas share almost no field names, so
this module maps both into :class:`~fresh_urban_forest.models.TreeRecord` and fills gaps
from the LiDAR canopy-height model.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np

from fresh_urban_forest.allometry import (
    estimate_crown_width_m,
    estimate_dbh_cm,
    estimate_height_m,
    is_native_species,
    profile_for,
    species_group,
)
from fresh_urban_forest.models import Building, TreeRecord, TreeStatus
from fresh_urban_forest.terrain import RasterData, project_lonlat, sample_raster_lonlat

BBox = tuple[float, float, float, float]


def load_ubc_trees(path: Path, *, bbox: BBox | None = None) -> list[TreeRecord]:
    """Load the UBC campus tree inventory from GeoJSON or CSV.

    Parameters
    ----------
    path : Path
        GeoJSON or CSV snapshot.
    bbox : tuple of float or None
        Optional ``(min_lon, min_lat, max_lon, max_lat)`` filter.

    Returns
    -------
    list of TreeRecord
        Normalised trees.
    """
    if path.suffix.lower() == ".csv":
        return _load_ubc_csv(path, bbox)
    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features", []) if isinstance(payload, Mapping) else []
    trees: list[TreeRecord] = []
    for feature in features:
        if not isinstance(feature, Mapping):
            continue
        geometry = feature.get("geometry", {})
        properties = feature.get("properties", {})
        if not isinstance(geometry, Mapping) or not isinstance(properties, Mapping):
            continue
        coordinates = geometry.get("coordinates", [])
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            continue
        lon = float(coordinates[0])
        lat = float(coordinates[1])
        if bbox and not _in_bbox(lon, lat, bbox):
            continue
        tree = _tree_from_ubc_properties(properties, lon, lat)
        if tree is not None:
            trees.append(tree)
    return trees


def load_vancouver_trees(path: Path, *, bbox: BBox | None = None) -> list[TreeRecord]:
    """Load the City of Vancouver public-tree CSV export.

    Parameters
    ----------
    path : Path
        CSV export from the open-data portal.
    bbox : tuple of float or None
        Optional ``(min_lon, min_lat, max_lon, max_lat)`` filter.

    Returns
    -------
    list of TreeRecord
        Normalised trees.
    """
    trees: list[TreeRecord] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            lon, lat = _vancouver_coordinates(row)
            if lon is None or lat is None:
                continue
            if bbox and not _in_bbox(lon, lat, bbox):
                continue
            genus = _clean(row.get("genus_name"))
            species = _clean(row.get("species_name"))
            cultivar = _clean(row.get("cultivar_name"))
            scientific = " ".join(part for part in (genus, species) if part and part != "NONE")
            if cultivar and cultivar != "NONE":
                scientific = f"{scientific} '{cultivar}'".strip()
            tree_id = (
                _clean(row.get("asset_id"))
                or _clean(row.get("tree_id"))
                or f"vancouver-{len(trees)}"
            )
            height = _to_float(row.get("height_m"))
            dbh = _to_float(row.get("diameter_cm"))
            trees.append(
                TreeRecord(
                    tree_id=f"vancouver:{tree_id}",
                    lon=lon,
                    lat=lat,
                    species=scientific,
                    common_name=_clean(row.get("common_name")),
                    genus=genus,
                    dbh_cm=dbh,
                    height_m=height,
                    crown_width_m=estimate_crown_width_m(dbh, species_group(scientific))
                    if dbh
                    else None,
                    crown_ratio=profile_for(scientific).crown_ratio,
                    status="alive",
                    source="vancouver_public_trees",
                    source_date=None,
                    native=is_native_species(scientific),
                    attributes={
                        "address": _clean(row.get("address")),
                        "local_area": _clean(row.get("local_area")),
                    },
                )
            )
    return trees


def enrich_trees(
    trees: Sequence[TreeRecord],
    dem: RasterData,
    chm: RasterData | None,
    *,
    crs: str | None = None,
) -> tuple[TreeRecord, ...]:
    """Attach projected coordinates, elevation, LiDAR height, and imputed attributes.

    Parameters
    ----------
    trees : sequence of TreeRecord
        Input trees.
    dem : RasterData
        Bare-earth elevation raster.
    chm : RasterData or None
        Canopy-height raster, aligned with the DEM.
    crs : str or None
        Target CRS. Defaults to the DEM CRS.

    Returns
    -------
    tuple of TreeRecord
        Enriched records, preserving order.
    """
    target_crs = crs or dem.crs
    if not trees:
        return ()
    lon = np.asarray([tree.lon for tree in trees], dtype=np.float64)
    lat = np.asarray([tree.lat for tree in trees], dtype=np.float64)
    elevations = sample_raster_lonlat(dem, lon, lat)
    canopy = sample_raster_lonlat(chm, lon, lat) if chm is not None else np.full(lon.shape, np.nan)
    enriched: list[TreeRecord] = []
    for index, tree in enumerate(trees):
        x, y = project_lonlat(tree.lon, tree.lat, target_crs)
        elevation = tree.elevation_m if tree.elevation_m is not None else _finite(elevations[index])
        lidar_height = (
            tree.lidar_height_m if tree.lidar_height_m is not None else _finite(canopy[index])
        )
        group = species_group(tree.species or tree.common_name)
        height = tree.height_m
        if height is None or height <= 0.5:
            if lidar_height is not None and 1.0 <= lidar_height <= 80.0:
                height = float(lidar_height)
            elif tree.dbh_cm is not None:
                height = estimate_height_m(tree.dbh_cm, group)
            else:
                height = 5.0
        dbh = tree.dbh_cm
        if dbh is None or dbh <= 0.5:
            dbh = estimate_dbh_cm(height, group)
        crown = tree.crown_width_m
        if crown is None or crown <= 0.2:
            crown = estimate_crown_width_m(dbh, group)
        ratio = (
            tree.crown_ratio
            if 0.05 <= tree.crown_ratio <= 1.0
            else profile_for(tree.species).crown_ratio
        )
        native = tree.native if tree.native is not None else is_native_species(tree.species)
        attributes = dict(tree.attributes)
        attributes.setdefault(
            "dbh_measured", "true" if tree.dbh_cm is not None and tree.dbh_cm > 0.5 else "false"
        )
        attributes.setdefault(
            "height_measured",
            "true" if tree.height_m is not None and tree.height_m > 0.5 else "false",
        )
        attributes.setdefault(
            "crown_width_measured",
            "true" if tree.crown_width_m is not None and tree.crown_width_m > 0.2 else "false",
        )
        attributes.setdefault("species_measured", "true" if bool(tree.species) else "false")
        enriched.append(
            TreeRecord(
                tree_id=tree.tree_id,
                lon=tree.lon,
                lat=tree.lat,
                species=tree.species,
                common_name=tree.common_name,
                genus=tree.genus,
                dbh_cm=round(float(dbh), 2),
                height_m=round(float(height), 2),
                crown_width_m=round(float(crown), 2),
                crown_ratio=round(float(ratio), 3),
                status=tree.status,
                source=tree.source,
                source_date=tree.source_date,
                native=native,
                x_m=round(x, 3),
                y_m=round(y, 3),
                elevation_m=None if elevation is None else round(elevation, 2),
                lidar_height_m=None if lidar_height is None else round(lidar_height, 2),
                attributes=attributes,
            )
        )
    return tuple(enriched)


def load_buildings(path: Path) -> tuple[Building, ...]:
    """Load building footprints from a GeoJSON FeatureCollection.

    Parameters
    ----------
    path : Path
        GeoJSON path.

    Returns
    -------
    tuple of Building
        Footprints with height and exterior rings.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features", []) if isinstance(payload, Mapping) else []
    buildings: list[Building] = []
    for feature in features:
        if not isinstance(feature, Mapping):
            continue
        geometry = feature.get("geometry", {})
        properties = feature.get("properties", {})
        if not isinstance(geometry, Mapping) or not isinstance(properties, Mapping):
            continue
        rings = _geometry_rings(geometry)
        if not rings:
            continue
        height = (
            _to_float(properties.get("BLDG_HEIGHT")) or _to_float(properties.get("height")) or 10.0
        )
        building_id = (
            _clean(properties.get("BLDG_UID"))
            or _clean(properties.get("id"))
            or f"building-{len(buildings)}"
        )
        name = _clean(properties.get("NAME")) or _clean(properties.get("name")) or building_id
        buildings.append(
            Building(
                building_id=building_id,
                name=name,
                height_m=float(height),
                rings=rings,
            )
        )
    return tuple(buildings)


def load_boundary(path: Path) -> tuple[tuple[float, float], ...]:
    """Load the first polygon ring from a GeoJSON boundary file.

    Parameters
    ----------
    path : Path
        GeoJSON path.

    Returns
    -------
    tuple of tuple of float
        Exterior ring in WGS84 ``(lon, lat)`` pairs.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features", []) if isinstance(payload, Mapping) else []
    for feature in features:
        if not isinstance(feature, Mapping):
            continue
        geometry = feature.get("geometry", {})
        if not isinstance(geometry, Mapping):
            continue
        rings = _geometry_rings(geometry)
        if rings:
            return rings[0]
    return ()


def _tree_from_ubc_properties(
    properties: Mapping[str, object], lon: float, lat: float
) -> TreeRecord | None:
    """Build a UBC tree record from one GeoJSON property mapping.

    Parameters
    ----------
    properties : mapping
        GeoJSON properties.
    lon : float
        Longitude.
    lat : float
        Latitude.

    Returns
    -------
    TreeRecord or None
        The tree, or ``None`` when the record has no usable identifier.
    """
    source_id = _clean(properties.get("TREEID")) or _clean(properties.get("OBJECTID"))
    if not source_id:
        return None
    taxa = _clean(properties.get("TAXA"))
    common = _clean(properties.get("COMMON_NAME"))
    dbh = _to_float(properties.get("DBH"))
    height = _to_float(properties.get("THEIGHT"))
    crown_1 = _to_float(properties.get("CROWNWIDTH1"))
    crown_2 = _to_float(properties.get("CROWNWIDTH2"))
    crown = _mean_optional(crown_1, crown_2)
    native = _yes_no(properties.get("NATIVE_TREE"))
    if native is None:
        native = is_native_species(taxa or common)
    status = _ubc_status(properties)
    return TreeRecord(
        tree_id=f"ubc:{source_id}",
        lon=lon,
        lat=lat,
        species=taxa,
        common_name=common,
        genus=taxa.split()[0] if taxa else "",
        dbh_cm=dbh,
        height_m=height,
        crown_width_m=crown,
        crown_ratio=profile_for(taxa or common).crown_ratio,
        status=status,
        source="ubc_campus_trees",
        source_date=_clean(properties.get("DATE_MEASURE"))
        or _clean(properties.get("TREE_ID_YR"))
        or None,
        native=native,
        attributes={
            "tree_type": _clean(properties.get("TREE_TYPE")),
            "tag": _clean(properties.get("TAG")),
            "crown_light_exposure": _clean(properties.get("CROWN_LIGHTEXP")),
        },
    )


def _load_ubc_csv(path: Path, bbox: BBox | None) -> list[TreeRecord]:
    """Load a UBC tree CSV snapshot.

    Parameters
    ----------
    path : Path
        CSV path.
    bbox : tuple of float or None
        Optional bounding box.

    Returns
    -------
    list of TreeRecord
        Normalised trees.
    """
    trees: list[TreeRecord] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            lon = _to_float(row.get("LONG") or row.get("lon") or row.get("longitude"))
            lat = _to_float(row.get("LAT") or row.get("lat") or row.get("latitude"))
            if lon is None or lat is None or (bbox and not _in_bbox(lon, lat, bbox)):
                continue
            properties: dict[str, object] = {str(key): value for key, value in row.items()}
            tree = _tree_from_ubc_properties(properties, lon, lat)
            if tree is not None:
                trees.append(tree)
    return trees


def _vancouver_coordinates(row: Mapping[str, str]) -> tuple[float | None, float | None]:
    """Extract coordinates from a Vancouver CSV row.

    Parameters
    ----------
    row : mapping
        CSV row.

    Returns
    -------
    tuple of float or None
        Longitude and latitude, or two ``None`` values.
    """
    lon = _to_float(row.get("geo_point_2d.lon"))
    lat = _to_float(row.get("geo_point_2d.lat"))
    if lon is not None and lat is not None:
        return (lon, lat)
    point = row.get("geo_point_2d", "")
    if point and "," in point:
        parts = [part.strip() for part in point.split(",", 1)]
        return (_to_float(parts[1]), _to_float(parts[0]))
    geom = row.get("geom", "")
    if geom:
        try:
            payload = json.loads(geom)
            coordinates = payload.get("coordinates", [])
            if isinstance(coordinates, list) and len(coordinates) >= 2:
                return (float(coordinates[0]), float(coordinates[1]))
        except (json.JSONDecodeError, TypeError, ValueError):
            return (None, None)
    return (None, None)


def _geometry_rings(geometry: Mapping[str, object]) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Extract polygon rings from a GeoJSON geometry.

    Parameters
    ----------
    geometry : mapping
        GeoJSON geometry.

    Returns
    -------
    tuple of tuple of tuple of float
        Rings, each a tuple of ``(lon, lat)`` pairs.
    """
    geometry_type = str(geometry.get("type", ""))
    coordinates = geometry.get("coordinates", [])
    if not isinstance(coordinates, list) or not coordinates:
        return ()
    polygons = (
        [coordinates]
        if geometry_type == "Polygon"
        else coordinates
        if geometry_type == "MultiPolygon"
        else []
    )
    rings: list[tuple[tuple[float, float], ...]] = []
    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon:
            continue
        exterior = polygon[0]
        if not isinstance(exterior, list):
            continue
        ring: list[tuple[float, float]] = []
        for point in exterior:
            if isinstance(point, list) and len(point) >= 2:
                ring.append((float(point[0]), float(point[1])))
        if len(ring) >= 3:
            rings.append(tuple(ring))
    return tuple(rings)


def _ubc_status(properties: Mapping[str, object]) -> TreeStatus:
    """Normalise the UBC live-tree and status fields.

    Parameters
    ----------
    properties : mapping
        Tree properties.

    Returns
    -------
    str
        A status accepted by :class:`TreeRecord`.
    """
    status = _clean(properties.get("TREE_STATUS")).lower()
    if "remov" in status or "dead" in status:
        return "dead" if "dead" in status else "removed"
    live = _yes_no(properties.get("LIVE_TREE"))
    if live is False:
        return "dead"
    return "alive"


def _in_bbox(lon: float, lat: float, bbox: BBox) -> bool:
    """Test whether a coordinate lies inside a bounding box.

    Parameters
    ----------
    lon : float
        Longitude.
    lat : float
        Latitude.
    bbox : tuple of float
        ``(min_lon, min_lat, max_lon, max_lat)``.

    Returns
    -------
    bool
        ``True`` when inside or on the boundary.
    """
    return bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]


def _clean(value: object) -> str:
    """Return a stripped string, treating null-like tokens as empty.

    Parameters
    ----------
    value : object
        Candidate value.

    Returns
    -------
    str
        Clean string.
    """
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "null", "<na>"} else text


def _to_float(value: object) -> float | None:
    """Convert a value to a finite float.

    Parameters
    ----------
    value : object
        Candidate value.

    Returns
    -------
    float or None
        The value, or ``None`` when it is empty or non-finite.
    """
    if value is None or value == "":
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def _yes_no(value: object) -> bool | None:
    """Interpret a yes/no field.

    Parameters
    ----------
    value : object
        Candidate value.

    Returns
    -------
    bool or None
        The interpretation, or ``None`` when ambiguous.
    """
    text = _clean(value).lower()
    if text in {"y", "yes", "true", "1"}:
        return True
    if text in {"n", "no", "false", "0"}:
        return False
    return None


def _mean_optional(first: float | None, second: float | None) -> float | None:
    """Average the finite values in a pair.

    Parameters
    ----------
    first : float or None
        First value.
    second : float or None
        Second value.

    Returns
    -------
    float or None
        The mean of the available values, or ``None``.
    """
    values = [value for value in (first, second) if value is not None and value > 0]
    return sum(values) / len(values) if values else None


def _finite(value: float) -> float | None:
    """Return a float when finite.

    Parameters
    ----------
    value : float
        Candidate value.

    Returns
    -------
    float or None
        The value, or ``None`` when non-finite.
    """
    return float(value) if np.isfinite(value) else None
