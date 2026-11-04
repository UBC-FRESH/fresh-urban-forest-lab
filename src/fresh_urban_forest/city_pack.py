"""Assemble a portable Vancouver city dataset for the existing web application."""

from __future__ import annotations

import datetime as dt
import gzip
import json
import math
import shutil
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import cast

import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon

from fresh_urban_forest.allometry import species_group, tree_carbon_kg, tree_crown_volume_m3
from fresh_urban_forest.dataset import write_dataset
from fresh_urban_forest.inventory import load_buildings
from fresh_urban_forest.metrics import SIZE_CLASSES, size_class
from fresh_urban_forest.models import (
    DATASET_SCHEMA_VERSION,
    Building,
    CanopyMetrics,
    DatasetManifest,
    SourceRecord,
    TreeRecord,
    UrbanForestDataset,
)
from fresh_urban_forest.terrain import (
    RasterData,
    build_terrain_grid,
    sample_raster_lonlat,
)


def build_city_pack(
    *,
    trees: tuple[TreeRecord, ...],
    city_metrics: Mapping[str, object],
    inventory_summary: Mapping[str, object],
    dem: RasterData,
    chm: RasterData,
    building_footprints: Path,
    building_height: RasterData,
    boundary: tuple[tuple[float, float], ...],
    sources: tuple[SourceRecord, ...],
    out_dir: Path,
    name: str = "City of Vancouver 2022 canopy pilot",
    max_trees: int = 30_000,
    max_buildings: int = 12_000,
    terrain_max_size: int = 900,
    generated_utc: str | None = None,
) -> UrbanForestDataset:
    """Build and write the city dataset directory.

    Parameters
    ----------
    trees : tuple of TreeRecord
        Full enriched inventory.
    city_metrics : mapping
        Output of :func:`fresh_urban_forest.city_metrics.compute_city_metrics`.
    inventory_summary : mapping
        Output of :func:`fresh_urban_forest.city_inventory.inventory_summary`.
    dem : RasterData
        City DEM.
    chm : RasterData
        City CHM.
    building_footprints : Path
        Building-footprint GeoJSON.
    building_height : RasterData
        Building-height raster.
    boundary : tuple of tuple of float
        City boundary ring in WGS84.
    sources : tuple of SourceRecord
        Provenance records.
    out_dir : Path
        Destination directory.
    name : str
        Dataset title.
    max_trees : int
        Visual tree sample size. Metrics always use the full inventory.
    max_buildings : int
        Visual building sample size.
    terrain_max_size : int
        Maximum terrain grid dimension.
    generated_utc : str or None
        Override timestamp for tests.

    Returns
    -------
    UrbanForestDataset
        The written dataset.
    """
    generated = generated_utc or dt.datetime.now(dt.UTC).isoformat()
    selected_trees = _select_visual_trees(trees, max_trees)
    buildings = _select_buildings(
        load_buildings(building_footprints),
        building_height,
        max_buildings,
    )
    terrain = build_terrain_grid(dem, chm, max_size=terrain_max_size)
    metrics = _canopy_metrics(trees, city_metrics)
    dataset_id = "vancouver-city-2022"
    manifest = DatasetManifest(
        schema_version=DATASET_SCHEMA_VERSION,
        dataset_id=dataset_id,
        name=name,
        generated_utc=generated,
        crs=dem.crs,
        bounds=dem.bounds,
        tree_count=len(trees),
        sources=sources,
        metrics=metrics,
        files={
            "manifest": "manifest.json",
            "trees": "trees.json",
            "metrics": "metrics.json",
            "terrain": "terrain.npz",
            "terrain_meta": "terrain.json",
            "buildings": "buildings.geojson",
            "boundary": "boundary.geojson",
            "city_metrics": "city_metrics.json",
            "inventory_summary": "inventory_summary.json",
            "map_trees": "map_trees.json.gz",
            "map_buildings": "map_buildings.geojson.gz",
        },
    )
    dataset = UrbanForestDataset(
        manifest=manifest,
        trees=tuple(selected_trees),
        terrain=terrain,
        buildings=buildings,
        boundary=boundary,
    )
    write_dataset(dataset, out_dir)
    (out_dir / "city_metrics.json").write_text(
        json.dumps(dict(city_metrics), indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "inventory_summary.json").write_text(
        json.dumps(dict(inventory_summary), indent=2) + "\n", encoding="utf-8"
    )
    with gzip.open(out_dir / "map_trees.json.gz", "wt", encoding="utf-8") as handle:
        json.dump(_map_tree_collection(trees), handle, separators=(",", ":"))
    with (
        open(building_footprints, "rb") as source,
        gzip.open(out_dir / "map_buildings.geojson.gz", "wb") as destination,
    ):
        shutil.copyfileobj(source, destination)
    return dataset


def _select_visual_trees(trees: tuple[TreeRecord, ...], max_trees: int) -> list[TreeRecord]:
    """Choose a height- and spatially representative visual sample."""
    if len(trees) <= max_trees:
        return list(trees)
    tallest = sorted(trees, key=lambda tree: -(tree.height_m or 0.0))[: max_trees // 2]
    chosen = {tree.tree_id for tree in tallest}
    remaining = [tree for tree in trees if tree.tree_id not in chosen]
    stride = max(1, math.ceil(len(remaining) / max(1, max_trees - len(tallest))))
    for tree in remaining[::stride]:
        chosen.add(tree.tree_id)
        if len(chosen) >= max_trees:
            break
    return [tree for tree in trees if tree.tree_id in chosen][:max_trees]


def _select_buildings(
    buildings: tuple[Building, ...],
    height_raster: RasterData,
    max_buildings: int,
) -> tuple[Building, ...]:
    """Assign LiDAR heights and pick a spatially stratified 3D building sample."""
    transformer = Transformer.from_crs("EPSG:4326", height_raster.crs, always_xy=True)
    buckets: dict[tuple[int, int], list[tuple[float, Building, float]]] = defaultdict(list)
    for building in buildings:
        if not building.rings or len(building.rings[0]) < 3:
            continue
        ring = building.rings[0]
        projected = [transformer.transform(lon, lat) for lon, lat in ring]
        area = Polygon(projected).area if len(projected) >= 3 else 0.0
        if area <= 0.0:
            continue
        lon = sum(point[0] for point in ring) / len(ring)
        lat = sum(point[1] for point in ring) / len(ring)
        sampled = sample_raster_lonlat(
            height_raster,
            np.asarray([lon], dtype=np.float64),
            np.asarray([lat], dtype=np.float64),
        )[0]
        height = float(sampled) if np.isfinite(sampled) and sampled > 0.5 else 8.0
        x, y = transformer.transform(lon, lat)
        cell = (math.floor(x / 300.0), math.floor(y / 300.0))
        buckets[cell].append((area, building, height))
    for bucket in buckets.values():
        bucket.sort(key=lambda item: -item[0])
    selected: list[tuple[float, Building, float]] = []
    keys = sorted(buckets)
    while len(selected) < max_buildings and any(buckets[key] for key in keys):
        for key in keys:
            if buckets[key] and len(selected) < max_buildings:
                selected.append(buckets[key].pop(0))
    if len(selected) < max_buildings:
        remaining = [item for key in keys for item in buckets[key]]
        remaining.sort(key=lambda item: -item[0])
        selected.extend(remaining[: max_buildings - len(selected)])
    return tuple(replace(building, height_m=round(height, 2)) for _, building, height in selected)


def _map_tree_collection(trees: tuple[TreeRecord, ...]) -> dict[str, object]:
    """Build the all-tree map layer with enough fields for the inspector."""
    features = []
    for tree in trees:
        group = species_group(tree.species or tree.common_name)
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [tree.lon, tree.lat]},
                "properties": {
                    "id": tree.tree_id,
                    "tree_id": tree.tree_id,
                    "lon": tree.lon,
                    "lat": tree.lat,
                    "species": tree.species,
                    "common_name": tree.common_name,
                    "genus": tree.genus,
                    "height": round(float(tree.height_m or 0.0), 2),
                    "crown_width": round(float(tree.crown_width_m or 0.0), 2),
                    "dbh_cm": round(float(tree.dbh_cm or 0.0), 2),
                    "crown_ratio": round(float(tree.crown_ratio), 3),
                    "group": group,
                    "native": bool(tree.native),
                    "status": tree.status,
                    "source": tree.source,
                    "carbon_kg": round(tree_carbon_kg(tree), 3),
                    "crown_volume_m3": round(tree_crown_volume_m3(tree), 3),
                    "color": _map_color(group, bool(tree.native)),
                    "measured": {
                        "dbh": str(tree.attributes.get("dbh_measured", "true")).lower()
                        in {"true", "1", "yes"},
                        "height": str(tree.attributes.get("height_measured", "true")).lower()
                        in {"true", "1", "yes"},
                        "crown_width": str(
                            tree.attributes.get("crown_width_measured", "true")
                        ).lower()
                        in {"true", "1", "yes"},
                        "species": bool(tree.species),
                    },
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _map_color(group: str, native: bool) -> str:
    """Return a high-contrast map colour for a tree group."""
    if group == "conifer":
        return "#14563a" if native else "#2c7350"
    if group == "deciduous":
        return "#6f963d" if native else "#91a948"
    return "#5f665f"


def _canopy_metrics(
    trees: tuple[TreeRecord, ...],
    city_metrics: Mapping[str, object],
) -> CanopyMetrics:
    """Build the shared metric object from the full inventory and city metrics."""
    city = cast(Mapping[str, object], city_metrics["city"])
    species_counts = Counter(tree.species or tree.common_name or "Unknown" for tree in trees)
    size_counts = Counter(
        size_class(tree.dbh_cm) for tree in trees if tree.dbh_cm is not None and tree.dbh_cm > 0
    )
    return CanopyMetrics(
        tree_count=int(cast(int, city["tree_count"])),
        species_count=len([name for name in species_counts if name != "Unknown"]),
        native_fraction=float(cast(float, city["native_fraction"])),
        canopy_cover_pct=float(cast(float, city["canopy_cover_pct"])),
        canopy_volume_m3=float(cast(float, city["canopy_volume_m3"])),
        mean_height_m=float(cast(float, city["tree_height_mean_m"])),
        p95_height_m=float(cast(float, city["tree_height_p95_m"])),
        total_carbon_kg=float(cast(float, city["carbon_kg"])),
        shannon_index=float(cast(float, city["shannon_index"])),
        size_classes=tuple((label, size_counts.get(label, 0)) for label, _, _ in SIZE_CLASSES),
        species_composition=tuple(species_counts.most_common(30)),
    )
