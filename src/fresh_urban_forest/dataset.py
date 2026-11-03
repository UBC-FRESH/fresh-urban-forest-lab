"""Build, write, and read a portable urban-forest dataset directory.

A dataset directory is self-describing: ``manifest.json`` names every other file and
records the metrics and provenance. The tree table stays JSON so a reviewer can inspect a
record without a columnar tool, while the terrain grid is a compressed NumPy archive.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from pathlib import Path

import numpy as np

from fresh_urban_forest.catalog import DatasetSource
from fresh_urban_forest.inventory import enrich_trees
from fresh_urban_forest.metrics import compute_metrics
from fresh_urban_forest.models import (
    DATASET_SCHEMA_VERSION,
    Building,
    DatasetManifest,
    SourceRecord,
    TerrainGrid,
    TreeRecord,
    UrbanForestDataset,
    metrics_from_dict,
    metrics_to_dict,
    tree_from_dict,
    tree_to_dict,
)
from fresh_urban_forest.terrain import (
    RasterData,
    build_terrain_grid,
    canopy_cover_pct,
    canopy_volume_m3,
)

MANIFEST_NAME = "manifest.json"


def build_dataset(
    *,
    name: str,
    trees: Sequence[TreeRecord],
    dem: RasterData,
    chm: RasterData | None,
    out_dir: Path,
    buildings: Sequence[Building] = (),
    boundary: Sequence[tuple[float, float]] = (),
    sources: Sequence[DatasetSource] = (),
    generated_utc: str | None = None,
) -> UrbanForestDataset:
    """Normalise inputs, calculate metrics, and write a dataset directory.

    Parameters
    ----------
    name : str
        Human-readable dataset name.
    trees : sequence of TreeRecord
        Raw tree inventory.
    dem : RasterData
        Bare-earth elevation raster.
    chm : RasterData or None
        Canopy-height raster aligned with the DEM.
    out_dir : Path
        Destination directory.
    buildings : sequence of Building
        Building footprints.
    boundary : sequence of tuple of float
        Boundary ring in WGS84.
    sources : sequence of DatasetSource
        Catalog entries that contributed.
    generated_utc : str or None
        Override for the generated timestamp, used by tests.

    Returns
    -------
    UrbanForestDataset
        The written dataset.
    """
    generated = generated_utc or _utc_now()
    enriched = enrich_trees(trees, dem, chm)
    area = max((dem.bounds[2] - dem.bounds[0]) * (dem.bounds[3] - dem.bounds[1]) / 10_000.0, 0.01)
    cover = canopy_cover_pct(chm.array, cell_area_m2=chm.cell_area_m2) if chm is not None else None
    volume = canopy_volume_m3(chm.array, cell_area_m2=chm.cell_area_m2) if chm is not None else None
    metrics = compute_metrics(
        enriched,
        area_ha=area,
        canopy_cover_pct_value=cover,
        canopy_volume_m3_value=volume,
    )
    terrain = build_terrain_grid(dem, chm)
    dataset_id = f"{_slug(name)}-{generated[:10].replace('-', '')}"
    manifest = DatasetManifest(
        schema_version=DATASET_SCHEMA_VERSION,
        dataset_id=dataset_id,
        name=name,
        generated_utc=generated,
        crs=dem.crs,
        bounds=dem.bounds,
        tree_count=len(enriched),
        sources=tuple(_source_record(source, generated) for source in sources),
        metrics=metrics,
        files={
            "manifest": MANIFEST_NAME,
            "trees": "trees.json",
            "metrics": "metrics.json",
            "terrain": "terrain.npz",
            "terrain_meta": "terrain.json",
            "buildings": "buildings.geojson",
            "boundary": "boundary.geojson",
        },
    )
    dataset = UrbanForestDataset(
        manifest=manifest,
        trees=enriched,
        terrain=terrain,
        buildings=tuple(buildings),
        boundary=tuple(boundary),
    )
    write_dataset(dataset, out_dir)
    return dataset


def write_dataset(dataset: UrbanForestDataset, out_dir: Path) -> Path:
    """Write a dataset directory.

    Parameters
    ----------
    dataset : UrbanForestDataset
        Dataset to write.
    out_dir : Path
        Destination directory.

    Returns
    -------
    Path
        The manifest path.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "trees.json").write_text(
        json.dumps([tree_to_dict(tree) for tree in dataset.trees], indent=1) + "\n",
        encoding="utf-8",
    )
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics_to_dict(dataset.manifest.metrics), indent=2) + "\n",
        encoding="utf-8",
    )
    np.savez_compressed(
        out_dir / "terrain.npz",
        elevation=np.asarray(dataset.terrain.elevation, dtype=np.float32),
        canopy_height=np.asarray(
            dataset.terrain.canopy_height
            if dataset.terrain.canopy_height is not None
            else np.zeros_like(dataset.terrain.elevation),
            dtype=np.float32,
        ),
    )
    terrain_meta = {
        "crs": dataset.terrain.crs,
        "bounds": list(dataset.terrain.bounds),
        "width": dataset.terrain.width,
        "height": dataset.terrain.height,
    }
    (out_dir / "terrain.json").write_text(
        json.dumps(terrain_meta, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "buildings.geojson").write_text(
        json.dumps(_buildings_geojson(dataset.buildings), indent=1) + "\n", encoding="utf-8"
    )
    (out_dir / "boundary.geojson").write_text(
        json.dumps(_boundary_geojson(dataset.boundary), indent=1) + "\n", encoding="utf-8"
    )
    (out_dir / MANIFEST_NAME).write_text(
        json.dumps(_manifest_dict(dataset.manifest), indent=2) + "\n", encoding="utf-8"
    )
    return out_dir / MANIFEST_NAME


def load_dataset(path: Path) -> UrbanForestDataset:
    """Read a dataset directory.

    Parameters
    ----------
    path : Path
        Dataset directory or manifest path.

    Returns
    -------
    UrbanForestDataset
        The loaded dataset.

    Raises
    ------
    FileNotFoundError
        When the manifest or a required file is missing.
    """
    root = path if path.is_dir() else path.parent
    manifest_path = root / MANIFEST_NAME
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    metrics_payload = json.loads((root / "metrics.json").read_text(encoding="utf-8"))
    tree_payload = json.loads((root / "trees.json").read_text(encoding="utf-8"))
    terrain_payload = json.loads((root / "terrain.json").read_text(encoding="utf-8"))
    with np.load(root / "terrain.npz", allow_pickle=False) as archive:
        elevation = np.asarray(archive["elevation"], dtype=np.float32)
        canopy = np.asarray(archive["canopy_height"], dtype=np.float32)
    terrain = TerrainGrid(
        crs=str(terrain_payload["crs"]),
        bounds=tuple(float(value) for value in terrain_payload["bounds"]),  # type: ignore[arg-type]
        width=int(terrain_payload["width"]),
        height=int(terrain_payload["height"]),
        elevation=elevation,
        canopy_height=canopy,
    )
    manifest = DatasetManifest(
        schema_version=str(payload["schema_version"]),
        dataset_id=str(payload["dataset_id"]),
        name=str(payload["name"]),
        generated_utc=str(payload["generated_utc"]),
        crs=str(payload["crs"]),
        bounds=tuple(float(value) for value in payload["bounds"]),  # type: ignore[arg-type]
        tree_count=int(payload["tree_count"]),
        sources=tuple(_source_from_dict(item) for item in payload.get("sources", [])),
        metrics=metrics_from_dict(metrics_payload),
        files={str(key): str(value) for key, value in payload.get("files", {}).items()},
    )
    buildings = _read_buildings(root / "buildings.geojson")
    boundary = _read_boundary(root / "boundary.geojson")
    return UrbanForestDataset(
        manifest=manifest,
        trees=tuple(tree_from_dict(item) for item in tree_payload),
        terrain=terrain,
        buildings=buildings,
        boundary=boundary,
    )


def dataset_summary(dataset: UrbanForestDataset) -> dict[str, object]:
    """Build a compact API summary for a dataset.

    Parameters
    ----------
    dataset : UrbanForestDataset
        Dataset to summarise.

    Returns
    -------
    dict
        Manifest fields and metrics without the full tree table.
    """
    return {
        "dataset_id": dataset.manifest.dataset_id,
        "name": dataset.manifest.name,
        "generated_utc": dataset.manifest.generated_utc,
        "crs": dataset.manifest.crs,
        "bounds": list(dataset.manifest.bounds),
        "tree_count": dataset.manifest.tree_count,
        "metrics": metrics_to_dict(dataset.manifest.metrics),
        "sources": [
            {
                "source_id": source.source_id,
                "title": source.title,
                "publisher": source.publisher,
                "url": source.url,
                "licence": source.licence,
                "access_mode": source.access_mode,
                "retrieved_utc": source.retrieved_utc,
                "checksum": source.checksum,
                "notes": source.notes,
            }
            for source in dataset.manifest.sources
        ],
        "files": dict(dataset.manifest.files),
    }


def _manifest_dict(manifest: DatasetManifest) -> dict[str, object]:
    """Convert a manifest to a JSON-safe dictionary.

    Parameters
    ----------
    manifest : DatasetManifest
        Manifest to convert.

    Returns
    -------
    dict
        JSON-safe dictionary.
    """
    return {
        "schema_version": manifest.schema_version,
        "dataset_id": manifest.dataset_id,
        "name": manifest.name,
        "generated_utc": manifest.generated_utc,
        "crs": manifest.crs,
        "bounds": list(manifest.bounds),
        "tree_count": manifest.tree_count,
        "metrics": metrics_to_dict(manifest.metrics),
        "sources": [asdict(source) for source in manifest.sources],
        "files": dict(manifest.files),
    }


def _source_record(source: DatasetSource, retrieved_utc: str) -> SourceRecord:
    """Build a provenance record from a catalog source.

    Parameters
    ----------
    source : DatasetSource
        Catalog entry.
    retrieved_utc : str
        Retrieval timestamp.

    Returns
    -------
    SourceRecord
        Provenance record.
    """
    return SourceRecord(
        source_id=source.source_id,
        title=source.title,
        publisher=source.publisher,
        url=source.url,
        licence=source.licence,
        access_mode=source.access_mode,
        retrieved_utc=retrieved_utc,
        checksum="",
        notes=source.notes,
    )


def _source_from_dict(item: object) -> SourceRecord:
    """Build a source record from a mapping.

    Parameters
    ----------
    item : object
        Mapping from ``manifest.json``.

    Returns
    -------
    SourceRecord
        Provenance record.
    """
    if not isinstance(item, Mapping):
        return SourceRecord("unknown", "unknown", "unknown", "", "unknown", "manual", "")
    return SourceRecord(
        source_id=str(item.get("source_id", "unknown")),
        title=str(item.get("title", "unknown")),
        publisher=str(item.get("publisher", "unknown")),
        url=str(item.get("url", "")),
        licence=str(item.get("licence", "unknown")),
        access_mode=str(item.get("access_mode", "manual")),
        retrieved_utc=str(item.get("retrieved_utc", "")),
        checksum=str(item.get("checksum", "")),
        notes=str(item.get("notes", "")),
    )


def _buildings_geojson(buildings: Sequence[Building]) -> dict[str, object]:
    """Convert buildings to a GeoJSON FeatureCollection.

    Parameters
    ----------
    buildings : sequence of Building
        Buildings to convert.

    Returns
    -------
    dict
        GeoJSON FeatureCollection.
    """
    features = []
    for building in buildings:
        polygons = [[[list(point) for point in ring] for ring in [ring]] for ring in building.rings]
        for ring in building.rings:
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "building_id": building.building_id,
                        "name": building.name,
                        "height_m": building.height_m,
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[list(point) for point in ring]],
                    },
                }
            )
        _ = polygons
    return {"type": "FeatureCollection", "features": features}


def _boundary_geojson(boundary: Sequence[tuple[float, float]]) -> dict[str, object]:
    """Convert a boundary ring to a GeoJSON FeatureCollection.

    Parameters
    ----------
    boundary : sequence of tuple of float
        Ring coordinates.

    Returns
    -------
    dict
        GeoJSON FeatureCollection.
    """
    if not boundary:
        return {"type": "FeatureCollection", "features": []}
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "analysis boundary"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[list(point) for point in boundary]],
                },
            }
        ],
    }


def _read_buildings(path: Path) -> tuple[Building, ...]:
    """Read buildings from a GeoJSON file written by :func:`write_dataset`.

    Parameters
    ----------
    path : Path
        GeoJSON path.

    Returns
    -------
    tuple of Building
        Buildings.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features", []) if isinstance(payload, Mapping) else []
    buildings: list[Building] = []
    for feature in features:
        if not isinstance(feature, Mapping):
            continue
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        if not isinstance(properties, Mapping) or not isinstance(geometry, Mapping):
            continue
        coordinates = geometry.get("coordinates", [])
        if not isinstance(coordinates, list) or not coordinates:
            continue
        ring = coordinates[0] if isinstance(coordinates[0], list) else []
        points = tuple(
            (float(point[0]), float(point[1])) for point in ring if isinstance(point, list)
        )
        if len(points) >= 3:
            buildings.append(
                Building(
                    building_id=str(properties.get("building_id", len(buildings))),
                    name=str(properties.get("name", "")),
                    height_m=float(properties.get("height_m", 10.0)),
                    rings=(points,),
                )
            )
    return tuple(buildings)


def _read_boundary(path: Path) -> tuple[tuple[float, float], ...]:
    """Read a boundary ring from a GeoJSON file.

    Parameters
    ----------
    path : Path
        GeoJSON path.

    Returns
    -------
    tuple of tuple of float
        Boundary ring.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features", []) if isinstance(payload, Mapping) else []
    if not features or not isinstance(features[0], Mapping):
        return ()
    geometry = features[0].get("geometry", {})
    if not isinstance(geometry, Mapping):
        return ()
    coordinates = geometry.get("coordinates", [])
    if not isinstance(coordinates, list) or not coordinates:
        return ()
    ring = coordinates[0] if isinstance(coordinates[0], list) else []
    return tuple((float(point[0]), float(point[1])) for point in ring if isinstance(point, list))


def _slug(value: str) -> str:
    """Convert a name to a short identifier.

    Parameters
    ----------
    value : str
        Input name.

    Returns
    -------
    str
        Lower-case hyphenated identifier.
    """
    return "".join(character if character.isalnum() else "-" for character in value.lower()).strip(
        "-"
    )


def _utc_now() -> str:
    """Return the current UTC time as an ISO string.

    Returns
    -------
    str
        ISO timestamp.
    """
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
