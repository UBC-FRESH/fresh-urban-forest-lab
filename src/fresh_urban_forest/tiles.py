"""Shared tile records and manifests for external LiDAR indexes.

LidarBC and CanElevation expose very different indexes: an ArcGIS feature service and a
large GeoPackage, respectively. Both are normalised into the same small tile record so the
rest of the pipeline can plan, download, hash, and report a tile set the same way.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from fresh_urban_forest.materialize import MaterializationRecord, download_file

TILE_MANIFEST_SCHEMA_VERSION = "fresh-urban-forest.tile-manifest.v1"


@dataclass(frozen=True, slots=True)
class LidarTile:
    """One downloadable LiDAR tile from an external index.

    Attributes
    ----------
    source : str
        Source identifier, such as ``lidarbc`` or ``canelevation``.
    tile_id : str
        Stable identifier within the source.
    filename : str
        Suggested local filename.
    url : str
        Direct download URL.
    year : int or None
        Acquisition year when published.
    projection : str
        Projection label from the index.
    density : float or None
        Published point density in points per square metre.
    bbox : tuple of float
        WGS84 ``(min_lon, min_lat, max_lon, max_lat)``.
    metadata_url : str
        Accuracy report or metadata URL, or an empty string.
    notes : str
        Source-specific caveats.
    """

    source: str
    tile_id: str
    filename: str
    url: str
    year: int | None
    projection: str
    density: float | None
    bbox: tuple[float, float, float, float]
    metadata_url: str = ""
    notes: str = ""


@dataclass(frozen=True, slots=True)
class TileManifest:
    """A JSON manifest of tiles selected for an area of interest.

    Attributes
    ----------
    schema_version : str
        Manifest schema identifier.
    source : str
        Source identifier.
    query_bbox : tuple of float
        WGS84 query bounding box.
    generated_utc : str
        ISO timestamp.
    tiles : tuple of LidarTile
        Selected tiles.
    """

    schema_version: str
    source: str
    query_bbox: tuple[float, float, float, float]
    generated_utc: str
    tiles: tuple[LidarTile, ...]


def write_tile_manifest(manifest: TileManifest, path: Path) -> Path:
    """Write a tile manifest as JSON.

    Parameters
    ----------
    manifest : TileManifest
        Manifest to write.
    path : Path
        Destination JSON path.

    Returns
    -------
    Path
        The written path.
    """
    payload = {
        "schema_version": manifest.schema_version,
        "source": manifest.source,
        "query_bbox": list(manifest.query_bbox),
        "generated_utc": manifest.generated_utc,
        "tile_count": len(manifest.tiles),
        "tiles": [_tile_to_dict(tile) for tile in manifest.tiles],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def read_tile_manifest(path: Path) -> TileManifest:
    """Read a tile manifest.

    Parameters
    ----------
    path : Path
        Manifest JSON path.

    Returns
    -------
    TileManifest
        The parsed manifest.

    Raises
    ------
    ValueError
        When the payload lacks a tile list.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_tiles = payload.get("tiles", [])
    if not isinstance(raw_tiles, list):
        raise ValueError("tile manifest has no tiles list")
    raw_bbox = payload.get("query_bbox", (0, 0, 0, 0))
    bbox_values = raw_bbox if isinstance(raw_bbox, (list, tuple)) else (0, 0, 0, 0)
    return TileManifest(
        schema_version=str(payload.get("schema_version", TILE_MANIFEST_SCHEMA_VERSION)),
        source=str(payload.get("source", "unknown")),
        query_bbox=(
            float(bbox_values[0]),
            float(bbox_values[1]),
            float(bbox_values[2]),
            float(bbox_values[3]),
        ),
        generated_utc=str(payload.get("generated_utc", "")),
        tiles=tuple(_tile_from_dict(item) for item in raw_tiles if isinstance(item, Mapping)),
    )


def download_tiles(
    tiles: Iterable[LidarTile],
    destination_root: Path,
    *,
    overwrite: bool = False,
) -> list[MaterializationRecord]:
    """Download selected tiles with the shared resumable downloader.

    Parameters
    ----------
    tiles : iterable of LidarTile
        Tiles to download.
    destination_root : Path
        Directory that receives the files.
    overwrite : bool
        When ``True``, re-download existing files. Otherwise an existing non-empty file is
        reused and hashed.

    Returns
    -------
    list of MaterializationRecord
        One record per tile.
    """
    records: list[MaterializationRecord] = []
    for tile in tiles:
        destination = destination_root / tile.source / tile.filename
        if destination.exists() and destination.stat().st_size > 0 and not overwrite:
            from fresh_urban_forest.materialize import sha256_file

            records.append(
                MaterializationRecord(
                    source_id=f"{tile.source}:{tile.tile_id}",
                    url=tile.url,
                    path=str(destination),
                    status="verified",
                    size_bytes=destination.stat().st_size,
                    sha256=sha256_file(destination),
                    attempts=0,
                    resumed_from_bytes=0,
                    message="reused existing file",
                    retrieved_utc=utc_now(),
                )
            )
            continue
        records.append(
            download_file(
                tile.url,
                destination,
                source_id=f"{tile.source}:{tile.tile_id}",
            )
        )
    return records


def tiles_to_geojson(manifest: TileManifest) -> dict[str, object]:
    """Convert a tile manifest to a GeoJSON FeatureCollection of bounding boxes.

    Parameters
    ----------
    manifest : TileManifest
        Manifest to convert.

    Returns
    -------
    dict
        GeoJSON FeatureCollection.
    """
    features = []
    for tile in manifest.tiles:
        west, south, east, north = tile.bbox
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[west, south], [east, south], [east, north], [west, north], [west, south]]
                    ],
                },
                "properties": {
                    "source": tile.source,
                    "tile_id": tile.tile_id,
                    "filename": tile.filename,
                    "url": tile.url,
                    "year": tile.year,
                    "projection": tile.projection,
                    "density": tile.density,
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


def make_manifest(
    source: str,
    query_bbox: tuple[float, float, float, float],
    tiles: Iterable[LidarTile],
) -> TileManifest:
    """Build a tile manifest with a generated timestamp.

    Parameters
    ----------
    source : str
        Source identifier.
    query_bbox : tuple of float
        WGS84 query bounding box.
    tiles : iterable of LidarTile
        Selected tiles.

    Returns
    -------
    TileManifest
        The manifest.
    """
    return TileManifest(
        schema_version=TILE_MANIFEST_SCHEMA_VERSION,
        source=source,
        query_bbox=query_bbox,
        generated_utc=utc_now(),
        tiles=tuple(tiles),
    )


def utc_now() -> str:
    """Return the current UTC timestamp.

    Returns
    -------
    str
        ISO timestamp with a ``Z`` suffix.
    """
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _tile_to_dict(tile: LidarTile) -> dict[str, object]:
    """Convert a tile to a JSON-safe dictionary.

    Parameters
    ----------
    tile : LidarTile
        Tile to convert.

    Returns
    -------
    dict
        JSON-safe tile.
    """
    return {
        "source": tile.source,
        "tile_id": tile.tile_id,
        "filename": tile.filename,
        "url": tile.url,
        "year": tile.year,
        "projection": tile.projection,
        "density": tile.density,
        "bbox": list(tile.bbox),
        "metadata_url": tile.metadata_url,
        "notes": tile.notes,
    }


def _tile_from_dict(data: Mapping[str, object]) -> LidarTile:
    """Build a tile from a manifest mapping.

    Parameters
    ----------
    data : mapping
        Tile mapping.

    Returns
    -------
    LidarTile
        The parsed tile.
    """
    raw_bbox = data.get("bbox", (0, 0, 0, 0))
    bbox_values = raw_bbox if isinstance(raw_bbox, (list, tuple)) else (0, 0, 0, 0)
    return LidarTile(
        source=str(data.get("source", "unknown")),
        tile_id=str(data.get("tile_id", "")),
        filename=str(data.get("filename", "")),
        url=str(data.get("url", "")),
        year=_optional_int(data.get("year")),
        projection=str(data.get("projection", "")),
        density=_optional_float(data.get("density")),
        bbox=(
            float(bbox_values[0]),
            float(bbox_values[1]),
            float(bbox_values[2]),
            float(bbox_values[3]),
        ),
        metadata_url=str(data.get("metadata_url", "")),
        notes=str(data.get("notes", "")),
    )


def _optional_int(value: object) -> int | None:
    """Convert an optional value to an integer.

    Parameters
    ----------
    value : object
        Candidate value.

    Returns
    -------
    int or None
        The integer, or ``None`` when empty or invalid.
    """
    if value is None or value == "":
        return None
    try:
        return int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _optional_float(value: object) -> float | None:
    """Convert an optional value to a float.

    Parameters
    ----------
    value : object
        Candidate value.

    Returns
    -------
    float or None
        The float, or ``None`` when empty or invalid.
    """
    if value is None or value == "":
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
