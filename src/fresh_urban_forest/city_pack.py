"""Assemble a portable Vancouver city dataset for the existing web application."""

from __future__ import annotations

import datetime as dt
import json
import math
from collections import Counter
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import cast

import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon

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
    """Assign LiDAR heights and select the largest footprints for the 3D scene."""
    transformer = Transformer.from_crs("EPSG:4326", height_raster.crs, always_xy=True)
    scored: list[tuple[float, Building, float]] = []
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
        scored.append((area, building, height))
    scored.sort(key=lambda item: -item[0])
    selected = scored[:max_buildings]
    return tuple(replace(building, height_m=round(height, 2)) for _, building, height in selected)


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
