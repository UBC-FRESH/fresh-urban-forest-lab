"""FRESH Urban Forest Lab.

A compact, reproducible urban-forest modelling stack. The public surface is the typed
dataset contract, the growth and decision-support functions, the scene builder, and the
FastAPI application. See ``docs/`` for the workflow and the data-source notes.
"""

from fresh_urban_forest.allometry import (
    aboveground_biomass_kg,
    carbon_kg,
    crown_volume_m3,
    estimate_crown_width_m,
    estimate_dbh_cm,
    estimate_height_m,
    grow_tree,
    is_native_species,
    species_group,
)
from fresh_urban_forest.catalog import Catalog, DatasetSource, load_catalog
from fresh_urban_forest.change import CanopyChange, canopy_change, change_grid
from fresh_urban_forest.change_product import build_change_product
from fresh_urban_forest.dataset import build_dataset, dataset_summary, load_dataset, write_dataset
from fresh_urban_forest.dss import (
    PlantingCandidate,
    ScenarioComparison,
    compare_scenarios,
    recommend_planting,
)
from fresh_urban_forest.growth import (
    apply_edits,
    competition_for_tree,
    project_scenario,
    scenario_summary,
)
from fresh_urban_forest.inventory import (
    enrich_trees,
    load_boundary,
    load_buildings,
    load_ubc_trees,
    load_vancouver_trees,
)
from fresh_urban_forest.itd import DetectedTree, detect_trees, detected_trees_geojson
from fresh_urban_forest.metrics import compare_metrics, compute_metrics
from fresh_urban_forest.models import (
    Building,
    CanopyMetrics,
    DatasetManifest,
    Scenario,
    ScenarioEdit,
    ScenarioResult,
    SourceRecord,
    TerrainGrid,
    TreeRecord,
    UrbanForestDataset,
)
from fresh_urban_forest.scene import build_scene
from fresh_urban_forest.terrain import (
    RasterData,
    build_terrain_grid,
    canopy_cover_pct,
    canopy_volume_m3,
    read_raster,
)

__all__ = [
    "Building",
    "CanopyChange",
    "CanopyMetrics",
    "Catalog",
    "DatasetManifest",
    "DatasetSource",
    "DetectedTree",
    "PlantingCandidate",
    "RasterData",
    "Scenario",
    "ScenarioComparison",
    "ScenarioEdit",
    "ScenarioResult",
    "SourceRecord",
    "TerrainGrid",
    "TreeRecord",
    "UrbanForestDataset",
    "aboveground_biomass_kg",
    "apply_edits",
    "build_change_product",
    "build_dataset",
    "build_scene",
    "build_terrain_grid",
    "canopy_change",
    "canopy_cover_pct",
    "canopy_volume_m3",
    "carbon_kg",
    "change_grid",
    "compare_metrics",
    "compare_scenarios",
    "competition_for_tree",
    "compute_metrics",
    "crown_volume_m3",
    "dataset_summary",
    "detect_trees",
    "detected_trees_geojson",
    "enrich_trees",
    "estimate_crown_width_m",
    "estimate_dbh_cm",
    "estimate_height_m",
    "grow_tree",
    "is_native_species",
    "load_boundary",
    "load_buildings",
    "load_catalog",
    "load_dataset",
    "load_ubc_trees",
    "load_vancouver_trees",
    "project_scenario",
    "read_raster",
    "recommend_planting",
    "scenario_summary",
    "species_group",
    "write_dataset",
]

__version__ = "0.1.0"
