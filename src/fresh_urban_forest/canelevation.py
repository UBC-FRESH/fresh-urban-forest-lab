"""Discover CanElevation point-cloud tiles from the NRCan tile index.

The federal product publishes a large GeoPackage index of 1 km tiles. The index carries
the provider, project, tile name, and direct S3 URL. Reading it with a bounding-box filter
is fast enough for an AOI query and avoids listing the whole bucket.
"""

from __future__ import annotations

import re
from pathlib import Path

from fresh_urban_forest.materialize import download_file
from fresh_urban_forest.tiles import LidarTile

CANELEVATION_TILE_INDEX_URL = (
    "https://canelevation-lidar-point-clouds.s3.ca-central-1.amazonaws.com/"
    "pointclouds_nuagespoints/Index_LiDARtiles_tuileslidar.gpkg"
)
CANELEVATION_TILE_INDEX_FILENAME = "Index_LiDARtiles_tuileslidar.gpkg"


def discover_canelevation_tiles(
    index_path: Path,
    bbox_wgs84: tuple[float, float, float, float],
    *,
    project: str | None = None,
    provider: str | None = None,
    limit: int | None = None,
) -> tuple[LidarTile, ...]:
    """Query the CanElevation tile index for tiles intersecting a bounding box.

    Parameters
    ----------
    index_path : Path
        The NRCan tile-index GeoPackage.
    bbox_wgs84 : tuple of float
        ``(min_lon, min_lat, max_lon, max_lat)``.
    project : str or None
        Optional project filter, for example ``Lower_Mainland_2016``.
    provider : str or None
        Optional provider filter, for example ``BC``.
    limit : int or None
        Maximum number of tiles to return.

    Returns
    -------
    tuple of LidarTile
        Matching tiles.

    Raises
    ------
    FileNotFoundError
        When the index is missing.
    RuntimeError
        When ``geopandas`` is not installed.
    """
    if not index_path.exists():
        raise FileNotFoundError(f"CanElevation index not found: {index_path}")
    try:
        import geopandas as gpd
    except ImportError as exc:  # pragma: no cover - exercised only in minimal installs
        raise RuntimeError("geopandas is required to read the CanElevation index") from exc
    padded = (
        bbox_wgs84[0] - 0.001,
        bbox_wgs84[1] - 0.001,
        bbox_wgs84[2] + 0.001,
        bbox_wgs84[3] + 0.001,
    )
    frame = gpd.read_file(index_path, bbox=padded)
    if "URL" not in frame.columns:
        raise ValueError("CanElevation index has no URL column")
    if project:
        frame = frame[frame["Project"].astype(str) == project]
    if provider:
        frame = frame[frame["Provider"].astype(str) == provider]
    frame = frame.sort_values("Tile_name")
    if limit is not None:
        frame = frame.head(max(0, limit))
    tiles: list[LidarTile] = []
    for _, row in frame.iterrows():
        url = str(row["URL"]).strip()
        if not url:
            continue
        geometry = row.geometry
        bounds = geometry.bounds if geometry is not None else (0.0, 0.0, 0.0, 0.0)
        filename = url.rsplit("/", 1)[-1]
        tile_name = str(row.get("Tile_name", filename))
        project_name = str(row.get("Project", ""))
        tiles.append(
            LidarTile(
                source="canelevation",
                tile_id=tile_name,
                filename=filename,
                url=url,
                year=_year_from_text(f"{project_name} {filename}"),
                projection=_projection_from_text(filename),
                density=None,
                bbox=(float(bounds[0]), float(bounds[1]), float(bounds[2]), float(bounds[3])),
                metadata_url="",
                notes=f"CanElevation provider {row.get('Provider', '')}; project {project_name}.",
            )
        )
    return tuple(tiles)


def download_canelevation_index(
    destination: Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Download the large CanElevation tile index.

    Parameters
    ----------
    destination : Path
        Destination directory.
    overwrite : bool
        Re-download an existing index.

    Returns
    -------
    Path
        The downloaded GeoPackage path.
    """
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / CANELEVATION_TILE_INDEX_FILENAME
    if target.exists() and target.stat().st_size > 0 and not overwrite:
        return target
    record = download_file(CANELEVATION_TILE_INDEX_URL, target, source_id="canelevation_index")
    if record.status != "verified":
        raise RuntimeError(f"CanElevation index download failed: {record.message}")
    return target


def _year_from_text(value: str) -> int | None:
    """Extract a plausible acquisition year from a project or filename.

    Parameters
    ----------
    value : str
        Text to search.

    Returns
    -------
    int or None
        The first four-digit year between 1990 and 2100.
    """
    for match in re.findall(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)", value):
        year = int(match)
        if 1990 <= year <= 2100:
            return year
    return None


def _projection_from_text(value: str) -> str:
    """Extract a UTM projection label from a tile filename.

    Parameters
    ----------
    value : str
        Tile filename.

    Returns
    -------
    str
        A label such as ``utm10``, or an empty string.
    """
    match = re.search(r"(utm\d{1,2})", value.lower())
    return match.group(1) if match else ""
