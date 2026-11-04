"""Command-line interface for the urban-forest lab.

The CLI is the reproducible path: catalog search, source materialization, dataset build,
dataset inspection, and the local web service. The browser is a view over the same typed
commands, not a separate implementation.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import tempfile
import zipfile
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from fresh_urban_forest.calibration import fit_allometry, write_allometry
from fresh_urban_forest.canelevation import (
    discover_canelevation_tiles,
    download_canelevation_index,
)
from fresh_urban_forest.catalog import DatasetSource, load_catalog
from fresh_urban_forest.change import canopy_change
from fresh_urban_forest.change_product import build_change_product
from fresh_urban_forest.dataset import build_dataset, dataset_summary, load_dataset
from fresh_urban_forest.demography import project_demography
from fresh_urban_forest.field_analysis import analyze_field_packet, write_field_analysis
from fresh_urban_forest.field_packet import build_field_packet
from fresh_urban_forest.ground_adapter import GroundAdapterParameters, write_ground_bundle
from fresh_urban_forest.habitat import GUILDS, guild_habitat, habitat_metrics, write_bird_report
from fresh_urban_forest.integration import build_lab_report, write_lab_report
from fresh_urban_forest.inventory import (
    load_boundary,
    load_buildings,
    load_ubc_trees,
    load_vancouver_trees,
)
from fresh_urban_forest.irrigation import compare_irrigation
from fresh_urban_forest.itd import detect_trees, detected_trees_geojson
from fresh_urban_forest.itd_postprocess import postprocess_trees
from fresh_urban_forest.lidar import PointCloudSummary, canopies_from_pair, summarize_point_cloud
from fresh_urban_forest.lidarbc import discover_lidarbc_tiles
from fresh_urban_forest.materialize import materialize_sources, read_materialization_manifest
from fresh_urban_forest.models import TerrainGrid, UrbanForestDataset, scenario_from_dict
from fresh_urban_forest.off_inventory import (
    detect_off_inventory,
    value_of_information,
    write_report,
    write_value_of_information,
)
from fresh_urban_forest.shade import (
    default_step_hours,
    shade_period,
    write_shade_product,
)
from fresh_urban_forest.solar import (
    parse_clock,
    parse_date,
    representative_time_grid,
    time_grid,
)
from fresh_urban_forest.species import profile_for_species, site_fit
from fresh_urban_forest.terrain import (
    RasterData,
    build_terrain_grid,
    crop_raster,
    project_lonlat,
    read_raster,
)
from fresh_urban_forest.tiles import (
    download_tiles,
    make_manifest,
    read_tile_manifest,
    write_tile_manifest,
)
from fresh_urban_forest.validation import (
    tune_detection,
    validate_detection,
    write_tuning,
    write_validation,
)
from fresh_urban_forest.vancouver import discover_vancouver_tiles
from fresh_urban_forest.water import compare_water_policies

app = typer.Typer(help="Open urban-forest LiDAR, inventory, growth, and 3-D decision support.")
catalog_app = typer.Typer(help="Inspect and materialize public data sources.")
tiles_app = typer.Typer(help="Discover and download LidarBC and CanElevation tiles.")
app.add_typer(catalog_app, name="catalog")
app.add_typer(tiles_app, name="tiles")
console = Console()

DEST_OPTION = typer.Option(..., "--dest", help="Destination directory.")
OUT_OPTION = typer.Option(..., "--out", help="Output dataset directory.")
GROUND_LAZ_OPTION = typer.Option(
    ...,
    "--laz",
    exists=True,
    dir_okay=False,
    help="Input LAS/LAZ tile.",
)
GROUND_OUT_OPTION = typer.Option(..., "--out", help="Output directory for the ground bundle.")
OUT_DIR_OPTION = typer.Option(..., "--out-dir", help="Output directory for a change product.")
NAME_OPTION = typer.Option("UBC urban forest", "--name", help="Dataset name.")
SOURCE_OPTION = typer.Option(None, "--source", help="Catalog source identifier; repeatable.")
ALL_DIRECT_OPTION = typer.Option(False, "--all-direct", help="Fetch every direct-download source.")
UBC_TREES_OPTION = typer.Option(..., "--ubc-trees", help="UBC tree GeoJSON or CSV.")
VANCOUVER_TREES_OPTION = typer.Option(None, "--vancouver-trees", help="City of Vancouver tree CSV.")
BUILDINGS_OPTION = typer.Option(None, "--buildings", help="Building footprint GeoJSON.")
BOUNDARY_OPTION = typer.Option(None, "--boundary", help="Boundary GeoJSON.")
DEM_OPTION = typer.Option(..., "--dem", help="Bare-earth DEM raster or zip.")
CHM_OPTION = typer.Option(None, "--chm", help="Canopy-height raster or zip.")
DSM_OPTION = typer.Option(
    None, "--dsm", help="Surface-model raster or zip; used when --chm is absent."
)
LAZ_OPTION = typer.Option(None, "--laz", help="Optional LAZ/LAS tile for point-cloud QA.")
BBOX_OPTION = typer.Option(
    None,
    "--bbox",
    help="WGS84 bounding box: min_lon,min_lat,max_lon,max_lat.",
)
MAX_TREES_OPTION = typer.Option(
    0, "--max-trees", help="Randomly sample at most this many trees; 0 keeps all."
)
DATASET_OPTION = typer.Option(..., "--dataset", help="Dataset directory.")
OPTIONAL_DATASET_OPTION = typer.Option(None, "--dataset", help="Optional dataset directory.")
HOST_OPTION = typer.Option("127.0.0.1", "--host", help="Bind address.")
PORT_OPTION = typer.Option(8000, "--port", help="Bind port.")
ALLOW_REMOTE_OPTION = typer.Option(False, "--allow-remote", help="Allow binding beyond loopback.")
RUNTIME_OPTION = typer.Option(None, "--runtime", help="Scenario runtime directory.")
ALLOW_AGENT_OPTION = typer.Option(
    False, "--allow-agent", help="Enable the local OpenCode assistant."
)
AGENT_MODEL_OPTION = typer.Option(
    "opencode-go/deepseek-v4.1-flash",
    "--agent-model",
    help="Model identifier for the assistant.",
)
AGENT_TIMEOUT_OPTION = typer.Option(
    300.0,
    "--agent-timeout",
    help="Assistant subprocess timeout in seconds.",
)
EARLIER_OPTION = typer.Option(..., "--earlier", help="Earlier dataset directory.")
LATER_OPTION = typer.Option(..., "--later", help="Later dataset directory.")
MIN_HEIGHT_OPTION = typer.Option(3.0, "--min-height", help="Minimum canopy height in metres.")
WINDOW_OPTION = typer.Option(3.0, "--window", help="Local-maxima window in metres.")
POSTPROCESS_OPTION = typer.Option(
    False, "--postprocess", help="Apply opt-in crown post-processing."
)
BUFFER_OPTION = typer.Option(10.0, "--buffer", help="Edge buffer in metres for post-processing.")
MAX_SMALL_HEIGHT_OPTION = typer.Option(
    2.0, "--max-small-height", help="Small-tree height threshold in metres."
)
MERGE_OPTION = typer.Option(
    True, "--merge/--no-merge", help="Conservatively merge overlapping crowns."
)
MERGE_AREA_RATIO_OPTION = typer.Option(
    0.6,
    "--merge-max-area-ratio",
    help="Maximum smaller/larger crown-area ratio for a merge.",
)
MERGE_HEIGHT_DELTA_OPTION = typer.Option(
    2.0,
    "--merge-max-height-delta",
    help="Maximum crown height difference for a merge.",
)
MERGE_GROUP_MEMBERS_OPTION = typer.Option(
    4,
    "--merge-max-group-members",
    help="Maximum source crowns in one merge group.",
)
MERGE_GROUP_EXTENT_OPTION = typer.Option(
    30.0,
    "--merge-max-group-extent",
    help="Maximum merge-group XY extent in metres.",
)
SUMMARY_OPTION = typer.Option(None, "--summary", help="Optional post-processing summary JSON path.")
THRESHOLD_OPTION = typer.Option(2.0, "--threshold", help="Canopy threshold in metres.")
LAYER_OPTION = typer.Option(4, "--layer", help="LidarBC ArcGIS layer id (4 is point cloud).")
INDEX_OPTION = typer.Option(..., "--index", help="CanElevation tile-index GeoPackage.")
PROJECT_OPTION = typer.Option(None, "--project", help="Optional CanElevation project filter.")
PROVIDER_OPTION = typer.Option(None, "--provider", help="Optional CanElevation provider filter.")
YEAR_OPTION = typer.Option(2022, "--year", help="Vancouver LiDAR year: 2013, 2018, or 2022.")
MANIFEST_OPTION = typer.Option(..., "--manifest", help="Tile manifest JSON.")
PACKET_OPTION = typer.Option(..., "--packet", help="Field packet directory.")
MAX_DISTANCE_OPTION = typer.Option(5.0, "--max-distance", help="Match distance in metres.")
MIN_HEIGHTS_OPTION = typer.Option(
    "3,4,5",
    "--min-heights",
    help="Comma-separated minimum heights to test.",
)
WINDOWS_OPTION = typer.Option(
    "3,4,5",
    "--windows",
    help="Comma-separated local-maxima windows to test.",
)
DATE_OPTION = typer.Option(None, "--date", help="ISO date for a shade request.")
TIMES_OPTION = typer.Option(
    None,
    "--times",
    help="Comma-separated local clock times, such as 09:00,12:00,15:00.",
)
MODE_OPTION = typer.Option("day", "--mode", help="instant, day, or annual.")
TARGET_HEIGHT_OPTION = typer.Option(
    1.5, "--target-height", help="Height above ground of the shade target plane."
)
SPECIES_OPTION = typer.Option("Acer rubrum", "--species", help="Species name.")
SUN_FRACTION_OPTION = typer.Option(0.6, "--sun-fraction", help="Sunlit fraction, 0 to 1.")
SOIL_VOLUME_OPTION = typer.Option(6.0, "--soil-volume", help="Available soil volume in m3.")
CROWN_AREA_OPTION = typer.Option(20.0, "--crown-area", help="Projected crown area in m2.")
AGE_OPTION = typer.Option(10.0, "--age", help="Tree age in years.")
SHADE_HOURS_OPTION = typer.Option(1000.0, "--shade-area-hours", help="Effective shade area-hours.")
SITES_OPTION = typer.Option(24, "--sites", help="Candidate sites in the optimization problem.")
BUDGET_OPTION = typer.Option(60_000.0, "--budget", help="Budget constraint in CAD.")
MAX_SITES_OPTION = typer.Option(40, "--max-sites", help="Maximum planted sites.")
POPULATION_OPTION = typer.Option(20, "--population", help="Fresh Solutions population size.")
GENERATIONS_OPTION = typer.Option(5, "--generations", help="Fresh Solutions generations.")
SCALARIZATIONS_OPTION = typer.Option(
    18, "--scalarizations", help="Number of weighted scalarizations."
)
LOCAL_ITERATIONS_OPTION = typer.Option(
    120, "--local-iterations", help="Fresh Solutions local-search iterations."
)
OPTIMIZE_WORKERS_OPTION = typer.Option(2, "--workers", help="Parallel scalarization workers.")
SURROGATE_SAMPLES_OPTION = typer.Option(
    0, "--surrogate-samples", help="Fit a screening surrogate on this many samples."
)
ARCHIVE_OPTION = typer.Option(..., "--archive", help="Optimization result JSON.")
SCENARIO_FILE_OPTION = typer.Option(None, "--scenario", help="Optional scenario JSON.")
PROJECT_YEAR_OPTION = typer.Option(None, "--year", help="Optional projection year.")
GRID_SIZE_OPTION = typer.Option(700, "--grid-size", help="Detection grid maximum rows/columns.")
MAX_CANDIDATES_OPTION = typer.Option(
    500, "--max-candidates", help="Maximum off-inventory candidates."
)
MIN_CONFIDENCE_OPTION = typer.Option(0.3, "--min-confidence", help="Minimum candidate confidence.")
VOI_OPTION = typer.Option(False, "--voi", help="Run the value-of-information experiment.")
VOI_SITES_OPTION = typer.Option(24, "--voi-sites", help="Sites in each VOI problem.")
VOI_SCALARIZATIONS_OPTION = typer.Option(
    8, "--voi-scalarizations", help="Scalarizations in each VOI problem."
)
VOI_WORKERS_OPTION = typer.Option(1, "--voi-workers", help="VOI solver workers.")
VOI_RADIUS_OPTION = typer.Option(
    700.0, "--voi-radius", help="VOI candidate-search radius in metres."
)
TRACE_OPTION = typer.Option(False, "--trace", help="Keep per-scalarization convergence histories.")


@catalog_app.command("list")
def catalog_list() -> None:
    """List every catalog source."""
    catalog = load_catalog()
    table = Table(title="Fresh Urban Forest source catalog")
    table.add_column("source_id")
    table.add_column("title")
    table.add_column("licence")
    table.add_column("access")
    table.add_column("products")
    for source in catalog.sources:
        table.add_row(
            source.source_id,
            source.title,
            source.licence,
            source.access_mode,
            ", ".join(source.products),
        )
    console.print(table)


@catalog_app.command("show")
def catalog_show(source_id: str) -> None:
    """Show one catalog source.

    Parameters
    ----------
    source_id : str
        Catalog identifier.
    """
    source = load_catalog().get(source_id)
    console.print_json(json.dumps(_source_payload(source)))


@catalog_app.command("search")
def catalog_search(query: str, limit: int = 10) -> None:
    """Search the catalog.

    Parameters
    ----------
    query : str
        Search text.
    limit : int
        Maximum results.
    """
    for source in load_catalog().search(query, limit=limit):
        console.print(f"[bold]{source.source_id}[/bold]  {source.title}  ({source.licence})")


@catalog_app.command("fetch")
def catalog_fetch(
    dest: Path = DEST_OPTION,
    source: list[str] | None = SOURCE_OPTION,
    all_direct: bool = ALL_DIRECT_OPTION,
) -> None:
    """Download direct sources with checksums and a manifest.

    Parameters
    ----------
    dest : Path
        Destination directory.
    source : list of str or None
        Source identifiers.
    all_direct : bool
        Fetch every direct source.
    """
    catalog = load_catalog()
    if all_direct:
        sources = [item for item in catalog.sources if item.is_direct]
    elif source:
        sources = [catalog.get(item) for item in source]
    else:
        raise typer.BadParameter("pass --source or --all-direct")
    records = materialize_sources(sources, dest, manifest_path=dest / "materialization.json")
    for record in records:
        console.print(
            f"{record.status:9s} {record.source_id}  {record.size_bytes} bytes  {record.path}"
        )


@app.command("build")
def build(
    ubc_trees: Path = UBC_TREES_OPTION,
    out: Path = OUT_OPTION,
    name: str = NAME_OPTION,
    vancouver_trees: Path | None = VANCOUVER_TREES_OPTION,
    buildings: Path | None = BUILDINGS_OPTION,
    boundary: Path | None = BOUNDARY_OPTION,
    dem: Path = DEM_OPTION,
    chm: Path | None = CHM_OPTION,
    dsm: Path | None = DSM_OPTION,
    laz: Path | None = LAZ_OPTION,
    bbox: str | None = BBOX_OPTION,
    max_trees: int = MAX_TREES_OPTION,
) -> None:
    """Build a portable dataset from inventory and LiDAR inputs.

    Parameters
    ----------
    ubc_trees : Path
        UBC tree inventory.
    out : Path
        Output directory.
    name : str
        Dataset name.
    vancouver_trees : Path or None
        Optional City of Vancouver tree CSV.
    buildings : Path or None
        Optional building footprint GeoJSON.
    boundary : Path or None
        Optional boundary GeoJSON.
    dem : Path
        DEM raster or zip.
    chm : Path or None
        CHM raster or zip.
    dsm : Path or None
        DSM raster or zip.
    laz : Path or None
        Optional LAZ point cloud for a QA summary.
    bbox : str or None
        WGS84 bounding box.
    max_trees : int
        Optional random sample size.
    """
    parsed_bbox = _parse_bbox(bbox)
    trees = list(load_ubc_trees(ubc_trees, bbox=parsed_bbox))
    if vancouver_trees is not None:
        trees.extend(load_vancouver_trees(vancouver_trees, bbox=parsed_bbox))
    if max_trees > 0 and len(trees) > max_trees:
        trees = trees[:max_trees]
    dem_data = read_raster(_resolve_raster(dem))
    chm_data = _resolve_chm(chm, dsm, dem_data)
    building_data = load_buildings(buildings) if buildings is not None else ()
    boundary_data = load_boundary(boundary) if boundary is not None else ()
    sources = _sources_for_inputs(ubc_trees, vancouver_trees, buildings, boundary, dem, chm, dsm)
    dataset = build_dataset(
        name=name,
        trees=trees,
        dem=dem_data,
        chm=chm_data,
        out_dir=out,
        buildings=building_data,
        boundary=boundary_data,
        sources=sources,
    )
    summary = dataset_summary(dataset)
    console.print_json(json.dumps(summary))
    if laz is not None:
        console.print_json(json.dumps(_point_cloud_payload(summarize_point_cloud(laz))))


@app.command("info")
def info(dataset: Path = DATASET_OPTION) -> None:
    """Print a dataset summary.

    Parameters
    ----------
    dataset : Path
        Dataset directory.
    """
    console.print_json(json.dumps(dataset_summary(load_dataset(dataset))))


@app.command("ground-adapter")
def ground_adapter(
    laz: Path = GROUND_LAZ_OPTION,
    out: Path = GROUND_OUT_OPTION,
    crs: str | None = typer.Option(None, "--crs"),
    vertical_datum: str | None = typer.Option(None, "--vertical-datum"),
    sor: bool = typer.Option(True, "--sor/--no-sor"),
    sor_k: int = typer.Option(10, "--sor-k"),
    sor_multiplier: float = typer.Option(2.0, "--sor-multiplier"),
    cell_size: float = typer.Option(1.0, "--cell-size"),
    max_angle: float = typer.Option(15.0, "--max-angle"),
    max_distance: float = typer.Option(0.5, "--max-distance"),
    max_iterations: int = typer.Option(8, "--max-iterations"),
    low_point_cut: float = typer.Option(0.15, "--low-point-cut"),
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Write an optional sidecar ground bundle for one LAS/LAZ tile.

    Parameters
    ----------
    laz : Path
        Input LAS or LAZ file.
    out : Path
        Output directory for ``ground.laz``, ``manifest.json``, and ``qa.json``.
    crs : str or None
        Explicit CRS label.
    vertical_datum : str or None
        Explicit vertical datum label.
    sor : bool
        Run statistical outlier removal before PTD.
    sor_k : int
        SOR neighbour count.
    sor_multiplier : float
        SOR standard-deviation multiplier.
    cell_size : float
        PTD seed grid cell size in metres.
    max_angle : float
        Maximum point-to-vertex angle in degrees.
    max_distance : float
        Maximum vertical residual in metres.
    max_iterations : int
        Maximum PTD iterations.
    low_point_cut : float
        Low-point cut in metres.
    overwrite : bool
        Replace an existing bundle.
    """
    parameters = GroundAdapterParameters(
        sor_enabled=sor,
        sor_k=sor_k,
        sor_multiplier=sor_multiplier,
        cell_size_m=cell_size,
        max_angle_deg=max_angle,
        max_distance_m=max_distance,
        max_iterations=max_iterations,
        low_point_cut_m=low_point_cut,
    )
    result = write_ground_bundle(
        laz,
        out,
        crs=crs,
        vertical_datum=vertical_datum,
        parameters=parameters,
        overwrite=overwrite,
    )
    console.print_json(
        json.dumps(
            {
                "ground_laz": str(result.ground_laz),
                "manifest_path": str(result.manifest_path),
                "qa_path": str(result.qa_path),
                "point_count": result.point_count,
                "ground_count": result.ground_count,
                "low_point_count": result.low_point_count,
                "warnings": list(result.warnings),
            }
        )
    )


@app.command("serve")
def serve(
    dataset: Path = DATASET_OPTION,
    host: str = HOST_OPTION,
    port: int = PORT_OPTION,
    allow_remote: bool = ALLOW_REMOTE_OPTION,
    runtime: Path | None = RUNTIME_OPTION,
    allow_agent: bool = ALLOW_AGENT_OPTION,
    agent_model: str = AGENT_MODEL_OPTION,
    agent_timeout: float = AGENT_TIMEOUT_OPTION,
) -> None:
    """Serve the local decision-support application.

    Parameters
    ----------
    dataset : Path
        Dataset directory.
    host : str
        Bind address.
    port : int
        Bind port.
    allow_remote : bool
        Allow a non-loopback bind address.
    runtime : Path or None
        Scenario runtime directory.
    allow_agent : bool
        Enable the local OpenCode assistant.
    agent_model : str
        Model identifier for the assistant.
    agent_timeout : float
        Assistant subprocess timeout in seconds.
    """
    if host not in {"127.0.0.1", "localhost", "::1"} and not allow_remote:
        raise typer.BadParameter("refusing a non-loopback bind without --allow-remote")
    import uvicorn

    from fresh_urban_forest.service import create_app

    app_instance = create_app(
        load_dataset(dataset),
        runtime_dir=runtime,
        allow_agent=allow_agent,
        agent_model=agent_model,
        agent_timeout=agent_timeout,
        dataset_root=dataset,
    )
    uvicorn.run(app_instance, host=host, port=port)


@tiles_app.command("lidarbc")
def tiles_lidarbc(
    bbox: str = BBOX_OPTION,
    out: Path = OUT_OPTION,
    layer: int = LAYER_OPTION,
) -> None:
    """Discover LidarBC tiles intersecting a WGS84 bounding box.

    Parameters
    ----------
    bbox : str
        ``min_lon,min_lat,max_lon,max_lat``.
    out : Path
        Output tile manifest JSON.
    layer : int
        LidarBC ArcGIS layer id.
    """
    parsed = _parse_bbox(bbox)
    if parsed is None:
        raise typer.BadParameter("--bbox is required")
    tiles = discover_lidarbc_tiles(parsed, layer_id=layer)
    write_tile_manifest(make_manifest("lidarbc", parsed, tiles), out)
    console.print(f"LidarBC: {len(tiles)} tiles -> {out}")


@tiles_app.command("vancouver")
def tiles_vancouver(
    bbox: str = BBOX_OPTION,
    out: Path = OUT_OPTION,
    year: int = YEAR_OPTION,
) -> None:
    """Discover City of Vancouver LiDAR tiles.

    Parameters
    ----------
    bbox : str
        ``min_lon,min_lat,max_lon,max_lat``.
    out : Path
        Output tile manifest JSON.
    year : int
        LiDAR year.
    """
    parsed = _parse_bbox(bbox)
    if parsed is None:
        raise typer.BadParameter("--bbox is required")
    tiles = discover_vancouver_tiles(year, parsed)
    write_tile_manifest(make_manifest(f"vancouver-lidar-{year}", parsed, tiles), out)
    console.print(f"Vancouver {year}: {len(tiles)} tiles -> {out}")


@tiles_app.command("canelevation")
def tiles_canelevation(
    index: Path = INDEX_OPTION,
    bbox: str = BBOX_OPTION,
    out: Path = OUT_OPTION,
    project: str | None = PROJECT_OPTION,
    provider: str | None = PROVIDER_OPTION,
) -> None:
    """Discover CanElevation tiles intersecting a WGS84 bounding box.

    Parameters
    ----------
    index : Path
        CanElevation tile-index GeoPackage.
    bbox : str
        ``min_lon,min_lat,max_lon,max_lat``.
    out : Path
        Output tile manifest JSON.
    project : str or None
        Optional project filter.
    provider : str or None
        Optional provider filter.
    """
    parsed = _parse_bbox(bbox)
    if parsed is None:
        raise typer.BadParameter("--bbox is required")
    tiles = discover_canelevation_tiles(
        index,
        parsed,
        project=project,
        provider=provider,
    )
    write_tile_manifest(make_manifest("canelevation", parsed, tiles), out)
    console.print(f"CanElevation: {len(tiles)} tiles -> {out}")


@tiles_app.command("index")
def tiles_index(dest: Path = DEST_OPTION, overwrite: bool = False) -> None:
    """Download the CanElevation tile index.

    Parameters
    ----------
    dest : Path
        Destination directory.
    overwrite : bool
        Re-download an existing index.
    """
    path = download_canelevation_index(dest, overwrite=overwrite)
    console.print(f"CanElevation index: {path} ({path.stat().st_size} bytes)")


@tiles_app.command("fetch")
def tiles_fetch(manifest: Path = MANIFEST_OPTION, dest: Path = DEST_OPTION) -> None:
    """Download every tile named in a manifest.

    Parameters
    ----------
    manifest : Path
        Tile manifest JSON.
    dest : Path
        Destination directory.
    """
    parsed = read_tile_manifest(manifest)
    records = download_tiles(parsed.tiles, dest)
    for record in records:
        console.print(f"{record.status:9s} {record.source_id}  {record.size_bytes} bytes")


@app.command("detect-trees")
def detect_trees_command(
    dataset: Path = DATASET_OPTION,
    out: Path = OUT_OPTION,
    min_height: float = MIN_HEIGHT_OPTION,
    window: float = WINDOW_OPTION,
    postprocess: bool = POSTPROCESS_OPTION,
    buffer: float = BUFFER_OPTION,
    max_small_height: float = MAX_SMALL_HEIGHT_OPTION,
    merge: bool = MERGE_OPTION,
    merge_max_area_ratio: float = MERGE_AREA_RATIO_OPTION,
    merge_max_height_delta: float = MERGE_HEIGHT_DELTA_OPTION,
    merge_max_group_members: int = MERGE_GROUP_MEMBERS_OPTION,
    merge_max_group_extent: float = MERGE_GROUP_EXTENT_OPTION,
    summary: Path | None = SUMMARY_OPTION,
) -> None:
    """Detect individual crowns from a dataset canopy-height grid.

    Parameters
    ----------
    dataset : Path
        Dataset directory.
    out : Path
        Output GeoJSON path.
    min_height : float
        Minimum canopy height in metres.
    window : float
        Local-maxima window in metres.
    postprocess : bool
        Apply opt-in buffer, small-tree, and merge post-processing.
    buffer : float
        Edge buffer in metres for post-processing.
    max_small_height : float
        Small-tree height threshold in metres.
    merge : bool
        Conservatively merge overlapping crowns.
    merge_max_area_ratio : float
        Maximum smaller/larger crown-area ratio for a merge.
    merge_max_height_delta : float
        Maximum crown height difference for a merge.
    merge_max_group_members : int
        Maximum source crowns in one merge group.
    merge_max_group_extent : float
        Maximum merge-group XY extent in metres.
    summary : Path or None
        Optional post-processing summary JSON path. Defaults to a sidecar next to ``out``.
    """
    loaded = load_dataset(dataset)
    trees = detect_trees(loaded.terrain, min_height_m=min_height, window_m=window)
    if postprocess:
        result = postprocess_trees(
            trees,
            loaded.terrain.bounds,
            buffer_m=buffer,
            max_small_height_m=max_small_height,
            merge=merge,
            merge_max_area_ratio=merge_max_area_ratio,
            merge_max_height_delta_m=merge_max_height_delta,
            merge_max_group_members=merge_max_group_members,
            merge_max_group_extent_m=merge_max_group_extent,
        )
        kept = result.kept()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(detected_trees_geojson(kept), indent=1) + "\n",
            encoding="utf-8",
        )
        summary_path = summary or out.with_suffix(".summary.json")
        summary_path.write_text(
            json.dumps(result.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
        console.print(
            f"Detected {len(trees)} crowns; kept {len(kept)} after post-processing; "
            f"summary -> {summary_path}"
        )
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(detected_trees_geojson(trees), indent=1) + "\n", encoding="utf-8")
    console.print(f"Detected {len(trees)} crowns and wrote {out}")


@app.command("change")
def change_command(
    earlier: Path = EARLIER_OPTION,
    later: Path = LATER_OPTION,
    out: Path = OUT_OPTION,
    threshold: float = THRESHOLD_OPTION,
) -> None:
    """Compare two datasets as repeat measures of canopy change.

    Parameters
    ----------
    earlier : Path
        Earlier dataset.
    later : Path
        Later dataset.
    out : Path
        Output JSON path.
    threshold : float
        Canopy threshold in metres.
    """
    first = load_dataset(earlier)
    second = load_dataset(later)
    if first.terrain.canopy_height is None or second.terrain.canopy_height is None:
        raise typer.BadParameter("both datasets need a canopy-height grid")
    result = canopy_change(
        first.terrain.canopy_height,
        second.terrain.canopy_height,
        threshold_m=threshold,
        cell_area_m2=1.0,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(asdict(result), indent=2) + "\n", encoding="utf-8")
    console.print_json(json.dumps(asdict(result)))


@app.command("field-packet")
def field_packet_command(
    dataset: Path = DATASET_OPTION,
    out_dir: Path = OUT_DIR_OPTION,
    bbox: str = BBOX_OPTION,
    chm: Path | None = CHM_OPTION,
    min_height: float = MIN_HEIGHT_OPTION,
    window: float = WINDOW_OPTION,
    max_trees: int = typer.Option(150, "--max-trees", help="Maximum trees in the packet."),
    max_distance: float = MAX_DISTANCE_OPTION,
) -> None:
    """Create a field-validation packet for a small reference patch.

    Parameters
    ----------
    dataset : Path
        Dataset directory.
    out_dir : Path
        Output packet directory.
    bbox : str
        Patch bounding box ``min_lon,min_lat,max_lon,max_lat``.
    chm : Path or None
        Optional full-resolution CHM.
    min_height : float
        Minimum detected canopy height.
    window : float
        Local-maxima window.
    max_trees : int
        Maximum inventory trees in the checklist.
    max_distance : float
        Match distance in metres.
    """
    parsed = _parse_bbox(bbox)
    if parsed is None:
        raise typer.BadParameter("--bbox is required")
    loaded = load_dataset(dataset)
    grid = _detection_grid(loaded, chm, parsed)
    detected = detect_trees(grid, min_height_m=min_height, window_m=window)
    validation = validate_detection(
        detected,
        loaded.trees,
        max_distance_m=max_distance,
        bbox_wgs84=parsed,
    )
    path = build_field_packet(
        loaded.trees,
        detected,
        bbox_wgs84=parsed,
        out_dir=out_dir,
        max_trees=max_trees,
        validation=validation,
    )
    console.print(f"Field packet: {path}")


@app.command("analyze-field-packet")
def analyze_field_packet_command(
    packet: Path = PACKET_OPTION,
    out_dir: Path = OUT_DIR_OPTION,
) -> None:
    """Analyse a completed field-validation packet.

    Parameters
    ----------
    packet : Path
        Packet directory with completed CSV files.
    out_dir : Path
        Output directory for JSON and Markdown.
    """
    result = analyze_field_packet(packet)
    path = write_field_analysis(result, out_dir)
    console.print(f"Field analysis: {path}")
    console.print(
        f"precision={result.precision} precision_merged={result.precision_including_merged} "
        f"recall={result.recall} height_bias={result.mean_height_bias_m} m"
    )


@app.command("tune-detection")
def tune_detection_command(
    dataset: Path = DATASET_OPTION,
    out: Path = OUT_OPTION,
    chm: Path | None = CHM_OPTION,
    bbox: str | None = BBOX_OPTION,
    min_heights: str = MIN_HEIGHTS_OPTION,
    windows: str = WINDOWS_OPTION,
    max_distance: float = MAX_DISTANCE_OPTION,
) -> None:
    """Sweep detection parameters and write a ranked tuning table.

    Parameters
    ----------
    dataset : Path
        Dataset directory.
    out : Path
        Output tuning JSON.
    chm : Path or None
        Optional full-resolution CHM raster.
    bbox : str or None
        Optional WGS84 bounding box.
    min_heights : str
        Comma-separated minimum heights.
    windows : str
        Comma-separated local-maxima windows.
    max_distance : float
        Match distance in metres.
    """
    loaded = load_dataset(dataset)
    parsed = _parse_bbox(bbox)
    grid = _detection_grid(loaded, chm, parsed)
    rows = tune_detection(
        grid,
        loaded.trees,
        bbox_wgs84=parsed,
        min_heights=_parse_float_list(min_heights),
        windows=_parse_float_list(windows),
        max_distance_m=max_distance,
    )
    write_tuning(rows, out)
    for row in rows[:5]:
        console.print(
            f"min_h={row.min_height_m} window={row.window_m} "
            f"detected={row.detected_count} matched={row.matched_count} "
            f"precision={row.precision} recall={row.recall} f1={row.f1}"
        )


@app.command("report")
def report_command(
    dataset: Path = DATASET_OPTION,
    out: Path = OUT_OPTION,
    scenario: Path | None = SCENARIO_FILE_OPTION,
    year: int | None = PROJECT_YEAR_OPTION,
) -> None:
    """Write the unified baseline or scenario lab report.

    Parameters
    ----------
    dataset : Path
        Dataset directory.
    out : Path
        Output JSON path.
    scenario : Path or None
        Optional scenario JSON.
    year : int or None
        Optional scenario year.
    """
    loaded = load_dataset(dataset)
    off_path = dataset / "off_inventory.json"
    off_inventory = None
    if off_path.exists():
        off_inventory = json.loads(off_path.read_text(encoding="utf-8"))
    if scenario is not None:
        parsed_scenario = scenario_from_dict(json.loads(scenario.read_text(encoding="utf-8")))
        from fresh_urban_forest.growth import project_scenario

        result = project_scenario(loaded, parsed_scenario, collect_trees=True)
        target = min(max(year or parsed_scenario.years, 0), parsed_scenario.years)
        report = build_lab_report(
            loaded,
            population=result.tree_timeline[target],
            metrics=result.metrics_by_year[target][1],
            scenario_id=parsed_scenario.scenario_id,
            scenario_name=parsed_scenario.name,
            year=target,
            off_inventory=off_inventory,
        )
    else:
        report = build_lab_report(loaded, off_inventory=off_inventory)
    path = write_lab_report(report, out)
    console.print(f"Lab report: {path}")


@app.command("birds")
def birds_command(
    dataset: Path = DATASET_OPTION,
    out: Path = OUT_OPTION,
    scenario: Path | None = SCENARIO_FILE_OPTION,
    year: int | None = PROJECT_YEAR_OPTION,
) -> None:
    """Write a bird habitat and prior-demography report.

    Parameters
    ----------
    dataset : Path
        Dataset directory.
    out : Path
        Output JSON path.
    scenario : Path or None
        Optional scenario JSON.
    year : int or None
        Optional projection year.
    """
    loaded = load_dataset(dataset)
    trees = loaded.trees
    target = 0
    if scenario is not None:
        parsed_scenario = scenario_from_dict(json.loads(scenario.read_text(encoding="utf-8")))
        target = min(max(year or parsed_scenario.years, 0), parsed_scenario.years)
        from fresh_urban_forest.growth import project_trees_to_year

        trees = project_trees_to_year(loaded, parsed_scenario, target)
    metrics = habitat_metrics(trees, loaded.terrain)
    guilds = []
    for guild in GUILDS:
        habitat = guild_habitat(metrics, guild)
        demography = project_demography(guild, habitat.suitability, years=25)
        guilds.append({**habitat.to_dict(), "demography": demography.to_dict()})
    payload = {
        "metrics": metrics.to_dict(),
        "guilds": guilds,
        "year": target,
        "evidence": metrics.evidence.to_dict(),
        "caveat": (
            "Relative abundance is a screening index, not a density. Demographic outputs "
            "are prior-driven, not local survival estimates."
        ),
    }
    path = write_bird_report(payload, out)
    console.print(f"Bird report: {path}")


@app.command("off-inventory")
def off_inventory_command(
    dataset: Path = DATASET_OPTION,
    out_dir: Path = OUT_DIR_OPTION,
    chm: Path | None = CHM_OPTION,
    bbox: str | None = BBOX_OPTION,
    min_height: float = MIN_HEIGHT_OPTION,
    window: float = WINDOW_OPTION,
    max_distance: float = MAX_DISTANCE_OPTION,
    grid_size: int = GRID_SIZE_OPTION,
    max_candidates: int = MAX_CANDIDATES_OPTION,
    min_confidence: float = MIN_CONFIDENCE_OPTION,
    voi: bool = VOI_OPTION,
    voi_sites: int = VOI_SITES_OPTION,
    voi_scalarizations: int = VOI_SCALARIZATIONS_OPTION,
    voi_workers: int = VOI_WORKERS_OPTION,
    voi_radius: float = VOI_RADIUS_OPTION,
) -> None:
    """Detect unmatched crowns and write an off-inventory candidate layer.

    Parameters
    ----------
    dataset : Path
        Dataset directory.
    out_dir : Path
        Output directory.
    chm : Path or None
        Optional higher-resolution CHM.
    bbox : str or None
        Optional WGS84 patch box.
    min_height : float
        Minimum detected canopy height.
    window : float
        Local-maxima window.
    max_distance : float
        Inventory match tolerance.
    grid_size : int
        Maximum detection-grid rows or columns.
    max_candidates : int
        Candidate cap.
    min_confidence : float
        Minimum candidate confidence.
    voi : bool
        Run the value-of-information experiment.
    voi_sites : int
        Sites per VOI problem.
    voi_scalarizations : int
        Scalarizations per VOI problem.
    voi_workers : int
        VOI solver workers.
    voi_radius : float
        VOI candidate-search radius.
    """
    loaded = load_dataset(dataset)
    parsed = _parse_bbox(bbox)
    if parsed is None:
        grid = loaded.terrain
    else:
        grid = _detection_grid(loaded, chm, parsed, max_size=grid_size)
    report = detect_off_inventory(
        loaded,
        grid,
        title=f"{loaded.manifest.name} off-inventory pilot",
        bbox_wgs84=parsed,
        min_height_m=min_height,
        window_m=window,
        max_distance_m=max_distance,
        min_confidence=min_confidence,
        max_candidates=max_candidates,
    )
    path = write_report(report, out_dir)
    console.print(
        f"Off-inventory: {report.candidate_count} candidates from "
        f"{report.detected_count} detected crowns -> {path}"
    )
    if voi:
        center = (
            ((parsed[0] + parsed[2]) / 2.0, (parsed[1] + parsed[3]) / 2.0)
            if parsed is not None
            else None
        )
        value = value_of_information(
            loaded,
            report,
            sites=voi_sites,
            scalarizations=voi_scalarizations,
            workers=voi_workers,
            center_lonlat=center,
            radius_m=voi_radius if center is not None else None,
        )
        voi_path = write_value_of_information(value, out_dir / "off_inventory_voi.json")
        console.print_json(json.dumps(value.to_dict()))
        console.print(f"Value of information: {voi_path}")


@app.command("fit-allometry")
def fit_allometry_command(
    dataset: Path = DATASET_OPTION,
    out: Path = OUT_OPTION,
    min_samples: int = typer.Option(20, "--min-samples", help="Minimum measured trees per group."),
) -> None:
    """Fit local height-diameter curves from measured inventory trees.

    Parameters
    ----------
    dataset : Path
        Dataset directory.
    out : Path
        Output JSON path.
    min_samples : int
        Minimum measured trees per species group.
    """
    loaded = load_dataset(dataset)
    fits = fit_allometry(loaded.trees, min_samples=min_samples)
    write_allometry(fits, out)
    for group, fit in fits.items():
        console.print(
            f"{group}: n={fit.sample_size} h=1.3+{fit.coefficient:.3f}*dbh^{fit.exponent:.3f} "
            f"rmse={fit.rmse_m} m r2={fit.r2}"
        )


@app.command("shade")
def shade_command(
    dataset: Path = DATASET_OPTION,
    date: str | None = DATE_OPTION,
    mode: str = MODE_OPTION,
    times: str | None = TIMES_OPTION,
    target_height: float = TARGET_HEIGHT_OPTION,
    out_dir: Path = OUT_DIR_OPTION,
    include_terrain: bool = typer.Option(
        True, "--include-terrain/--no-terrain", help="Include the coarse terrain horizon."
    ),
) -> None:
    """Build a shade summary, PNG overlay, and NPZ grid for a dataset.

    Parameters
    ----------
    dataset : Path
        Dataset directory.
    date : str or None
        ISO date. Defaults to today.
    mode : str
        ``instant``, ``day``, or ``annual``.
    times : str or None
        Comma-separated local clock times.
    target_height : float
        Height above ground of the target plane.
    out_dir : Path
        Output directory.
    include_terrain : bool
        Include the coarse terrain horizon.
    """
    loaded = load_dataset(dataset)
    _day, whens, step = _cli_shade_whens(date, mode, times)
    period = shade_period(
        loaded,
        whens,
        target_height_m=target_height,
        step_hours=step,
        include_terrain=include_terrain,
    )
    path = write_shade_product(period, out_dir)
    console.print(f"Shade product: {path}")
    console.print_json(json.dumps(period.metrics))


@app.command("species-fit")
def species_fit_command(
    species: str = SPECIES_OPTION,
    sun_fraction: float = SUN_FRACTION_OPTION,
    soil_volume: float = SOIL_VOLUME_OPTION,
    out: Path = OUT_OPTION,
    dataset: Path | None = OPTIONAL_DATASET_OPTION,
) -> None:
    """Score a species against a site.

    Parameters
    ----------
    species : str
        Species name.
    sun_fraction : float
        Fraction of daylight the site is sunlit.
    soil_volume : float
        Available soil volume.
    out : Path
        Output JSON path.
    dataset : Path or None
        Optional dataset directory, used only for context in the output.
    """
    loaded = load_dataset(dataset) if dataset is not None else None
    profile = profile_for_species(species)
    fit = site_fit(profile, sun_fraction=sun_fraction, soil_volume_m3=soil_volume)
    payload = {
        "dataset_id": loaded.manifest.dataset_id if loaded is not None else "",
        "profile": profile.to_dict(),
        "fit": fit.to_dict(),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    console.print(f"Species fit: {out}")


@app.command("water")
def water_command(
    species: str = SPECIES_OPTION,
    sun_fraction: float = SUN_FRACTION_OPTION,
    soil_volume: float = SOIL_VOLUME_OPTION,
    crown_area: float = CROWN_AREA_OPTION,
    age: float = AGE_OPTION,
    out: Path = OUT_OPTION,
    dataset: Path | None = OPTIONAL_DATASET_OPTION,
) -> None:
    """Build an annual water balance and policy comparison.

    Parameters
    ----------
    species : str
        Species name.
    sun_fraction : float
        Fraction of daylight the site is sunlit.
    soil_volume : float
        Available soil volume.
    crown_area : float
        Projected crown area.
    age : float
        Tree age.
    out : Path
        Output JSON path.
    dataset : Path or None
        Optional dataset directory, used only for context in the output.
    """
    loaded = load_dataset(dataset) if dataset is not None else None
    profile = profile_for_species(species)
    options = compare_water_policies(
        profile,
        crown_area_m2=crown_area,
        soil_volume_m3=soil_volume,
        sun_fraction=sun_fraction,
        age_years=age,
    )
    payload = {
        "dataset_id": loaded.manifest.dataset_id if loaded is not None else "",
        "policies": [option.to_dict() for option in options],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    console.print(f"Water balance: {out}")


@app.command("irrigation")
def irrigation_command(
    species: str = SPECIES_OPTION,
    sun_fraction: float = SUN_FRACTION_OPTION,
    soil_volume: float = SOIL_VOLUME_OPTION,
    crown_area: float = CROWN_AREA_OPTION,
    age: float = AGE_OPTION,
    shade_area_hours: float = SHADE_HOURS_OPTION,
    out: Path = OUT_OPTION,
    dataset: Path | None = OPTIONAL_DATASET_OPTION,
) -> None:
    """Compare irrigation policies and cost per shade-hour.

    Parameters
    ----------
    species : str
        Species name.
    sun_fraction : float
        Fraction of daylight the site is sunlit.
    soil_volume : float
        Available soil volume.
    crown_area : float
        Projected crown area.
    age : float
        Tree age.
    shade_area_hours : float
        Effective shade area-hours.
    out : Path
        Output JSON path.
    dataset : Path or None
        Optional dataset directory, used only for context in the output.
    """
    loaded = load_dataset(dataset) if dataset is not None else None
    profile = profile_for_species(species)
    options = compare_irrigation(
        profile,
        crown_area_m2=crown_area,
        soil_volume_m3=soil_volume,
        sun_fraction=sun_fraction,
        shade_area_hours=shade_area_hours,
        age_years=age,
    )
    payload = {
        "dataset_id": loaded.manifest.dataset_id if loaded is not None else "",
        "options": [option.to_dict() for option in options],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    console.print(f"Irrigation options: {out}")


def _cli_shade_whens(
    date_value: str | None,
    mode: str,
    times_value: str | None,
) -> tuple[dt.date, tuple[dt.datetime, ...], float]:
    """Build CLI shade times.

    Parameters
    ----------
    date_value : str or None
        ISO date, or ``None`` for today.
    mode : str
        ``instant``, ``day``, or ``annual``.
    times_value : str or None
        Comma-separated clock times.

    Returns
    -------
    tuple
        Date, aware datetimes, and step hours.

    Raises
    ------
    typer.BadParameter
        When the date or a time is invalid.
    """
    try:
        day = parse_date(date_value) if date_value else dt.date.today()
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if mode == "annual":
        return (day, representative_time_grid(day.year), 3.0)
    raw = [part.strip() for part in (times_value or "").split(",") if part.strip()]
    if not raw:
        raw = (
            ["12:00"]
            if mode == "instant"
            else ["08:00", "10:00", "12:00", "14:00", "16:00", "18:00"]
        )
    if mode == "instant":
        raw = raw[:1]
    try:
        for value in raw:
            parse_clock(value)
        whens = time_grid(day, times=raw)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    step = 1.0 if mode == "instant" else default_step_hours(whens)
    return (day, whens, step)


@app.command("optimize")
def optimize_command(
    dataset: Path = DATASET_OPTION,
    out: Path = OUT_OPTION,
    sites: int = SITES_OPTION,
    horizon: int = typer.Option(20, "--horizon", help="Projection horizon in years."),
    budget: float = BUDGET_OPTION,
    max_sites: int = MAX_SITES_OPTION,
    population: int = POPULATION_OPTION,
    generations: int = GENERATIONS_OPTION,
    scalarizations: int = SCALARIZATIONS_OPTION,
    local_iterations: int = LOCAL_ITERATIONS_OPTION,
    workers: int = OPTIMIZE_WORKERS_OPTION,
    seed: int = typer.Option(42, "--seed", help="Search seed."),
    surrogate_samples: int = SURROGATE_SAMPLES_OPTION,
    trace: bool = TRACE_OPTION,
) -> None:
    """Solve a planting problem with Fresh Solutions and write the archive.

    Parameters
    ----------
    dataset : Path
        Dataset directory.
    out : Path
        Output result JSON.
    sites : int
        Number of candidate sites.
    horizon : int
        Projection horizon.
    budget : float
        Budget constraint in CAD.
    max_sites : int
        Maximum planted sites.
    population : int
        Fresh Solutions population size.
    generations : int
        Fresh Solutions generations.
    scalarizations : int
        Number of weighted scalarizations.
    local_iterations : int
        Local-search iterations per scalarization.
    workers : int
        Parallel scalarization workers.
    seed : int
        Search seed.
    surrogate_samples : int
        Optional screening surrogate sample count.
    trace : bool
        Keep per-scalarization convergence histories.
    """
    from fresh_urban_forest.optimize import build_problem, run_optimization, write_result

    loaded = load_dataset(dataset)
    problem = build_problem(
        loaded,
        site_count=sites,
        horizon=horizon,
        budget_cad=budget,
        max_sites=max_sites,
        seed=seed,
    )
    result = run_optimization(
        problem,
        population_size=population,
        generations=generations,
        scalarizations=scalarizations,
        local_iterations=local_iterations,
        workers=workers,
        seed=seed,
        surrogate_samples=surrogate_samples,
        trace=trace,
    )
    path = write_result(result, out)
    console.print(f"Optimization result: {path}")
    console.print(
        f"archive={len(result.archive.solutions)} hypervolume={result.archive.hypervolume:.4f} "
        f"evaluations={result.evaluations} runtime={result.runtime_s:.2f}s"
    )


@app.command("pareto")
def pareto_command(
    archive: Path = ARCHIVE_OPTION,
    out: Path = OUT_OPTION,
) -> None:
    """Summarise a saved optimization archive.

    Parameters
    ----------
    archive : Path
        Optimization result JSON.
    out : Path
        Output summary JSON.
    """
    payload = json.loads(archive.read_text(encoding="utf-8"))
    archive_payload = payload.get("archive", {})
    if not isinstance(archive_payload, Mapping):
        raise typer.BadParameter("archive payload is not an object")
    solutions = archive_payload.get("solutions", [])
    if not isinstance(solutions, list):
        raise typer.BadParameter("archive solutions are not a list")
    summary = {
        "problem_id": archive_payload.get("problem_id", ""),
        "objectives": archive_payload.get("objectives", []),
        "solution_count": len(solutions),
        "hypervolume": archive_payload.get("hypervolume", 0.0),
        "top_robust": sorted(
            solutions,
            key=lambda item: (
                float(item.get("robustness", 0.0)) if isinstance(item, Mapping) else 0.0
            ),
            reverse=True,
        )[:5],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    console.print(
        f"Archive: {summary['solution_count']} solutions, "
        f"hypervolume {summary['hypervolume']} -> {out}"
    )


def _detection_grid(
    loaded: UrbanForestDataset,
    chm: Path | None,
    bbox: tuple[float, float, float, float] | None,
    *,
    max_size: int = 1600,
) -> TerrainGrid:
    """Build a detection grid from a CHM or a dataset terrain.

    Parameters
    ----------
    loaded : object
        Loaded dataset.
    chm : Path or None
        Optional full-resolution CHM.
    bbox : tuple of float or None
        Optional WGS84 bounding box.
    max_size : int
        Maximum rows or columns in the detection grid.

    Returns
    -------
    object
        Terrain grid.
    """
    if chm is None:
        return loaded.terrain
    raster = read_raster(_resolve_raster(chm))
    if bbox is not None:
        xs: list[float] = []
        ys: list[float] = []
        for lon, lat in (
            (bbox[0], bbox[1]),
            (bbox[2], bbox[1]),
            (bbox[2], bbox[3]),
            (bbox[0], bbox[3]),
        ):
            x, y = project_lonlat(lon, lat, raster.crs)
            xs.append(x)
            ys.append(y)
        raster = crop_raster(raster, (min(xs), min(ys), max(xs), max(ys)))
    return build_terrain_grid(raster, raster, max_size=max_size)


def _parse_float_list(value: str) -> tuple[float, ...]:
    """Parse a comma-separated float list.

    Parameters
    ----------
    value : str
        Comma-separated values.

    Returns
    -------
    tuple of float
        Parsed values.

    Raises
    ------
    typer.BadParameter
        When a value is not numeric.
    """
    try:
        return tuple(float(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise typer.BadParameter("expected comma-separated numbers") from exc


@app.command("validate-detection")
def validate_detection_command(
    dataset: Path = DATASET_OPTION,
    out_dir: Path = OUT_DIR_OPTION,
    chm: Path | None = CHM_OPTION,
    bbox: str | None = BBOX_OPTION,
    min_height: float = MIN_HEIGHT_OPTION,
    window: float = WINDOW_OPTION,
    max_distance: float = MAX_DISTANCE_OPTION,
) -> None:
    """Validate CHM tree detection against the inventory.

    Parameters
    ----------
    dataset : Path
        Dataset directory.
    out_dir : Path
        Output directory for the validation JSON and GeoJSON.
    chm : Path or None
        Optional full-resolution CHM raster. When omitted, the dataset terrain grid is used.
    bbox : str or None
        Optional WGS84 bounding box.
    min_height : float
        Minimum detected canopy height in metres.
    window : float
        Local-maxima window in metres.
    max_distance : float
        Maximum match distance in metres.
    """
    loaded = load_dataset(dataset)
    parsed = _parse_bbox(bbox)
    grid = _detection_grid(loaded, chm, parsed)
    detected = detect_trees(grid, min_height_m=min_height, window_m=window)
    result = validate_detection(
        detected,
        loaded.trees,
        max_distance_m=max_distance,
        bbox_wgs84=parsed,
    )
    path = write_validation(result, out_dir)
    console.print(f"Validation: {path}")
    console.print(
        f"detected={result.detected_count} inventory={result.inventory_count} "
        f"matched={result.matched_count} precision={result.precision} recall={result.recall} "
        f"f1={result.f1} height_bias={result.mean_height_delta_m} m"
    )


@app.command("build-change")
def build_change(
    earlier: Path = EARLIER_OPTION,
    later: Path = LATER_OPTION,
    out_dir: Path = OUT_DIR_OPTION,
    threshold: float = THRESHOLD_OPTION,
) -> None:
    """Build an observed-change product from two datasets.

    Parameters
    ----------
    earlier : Path
        Earlier dataset directory.
    later : Path
        Later dataset directory.
    out_dir : Path
        Output change-product directory.
    threshold : float
        Canopy threshold in metres.
    """
    first = load_dataset(earlier)
    second = load_dataset(later)
    if first.terrain.canopy_height is None or second.terrain.canopy_height is None:
        raise typer.BadParameter("both datasets need a canopy-height grid")
    path = build_change_product(
        first.terrain,
        second.terrain,
        out_dir,
        threshold_m=threshold,
        earlier_label=first.manifest.name,
        later_label=second.manifest.name,
    )
    console.print(f"Change product: {path}")


@app.command("materialization")
def materialization_status(dest: Path = DEST_OPTION) -> None:
    """Print the records in a materialization manifest.

    Parameters
    ----------
    dest : Path
        Directory that contains ``materialization.json``.
    """
    records = read_materialization_manifest(dest / "materialization.json")
    for record in records:
        console.print(
            f"{record.get('status', '?'):9s} {record.get('source_id', '?'):28s} "
            f"{record.get('size_bytes', 0)} bytes"
        )


def _resolve_chm(
    chm: Path | None,
    dsm: Path | None,
    dem: RasterData,
) -> RasterData | None:
    """Resolve a CHM from a CHM path or a DSM-DEM pair.

    Parameters
    ----------
    chm : Path or None
        CHM raster or zip.
    dsm : Path or None
        DSM raster or zip.
    dem : RasterData
        DEM used as the fallback base for a DSM-DEM difference.

    Returns
    -------
    RasterData or None
        Canopy height, or ``None`` when neither input is available.
    """
    if chm is not None:
        return read_raster(_resolve_raster(chm))
    if dsm is not None:
        return canopies_from_pair(_resolve_raster(dsm), dem.path)
    return None


def _resolve_raster(path: Path) -> Path:
    """Return a raster path, extracting a zip when needed.

    Parameters
    ----------
    path : Path
        Raster or zip path.

    Returns
    -------
    Path
        Extracted or original raster path.

    Raises
    ------
    FileNotFoundError
        When the zip has no GeoTIFF member.
    """
    if path.suffix.lower() != ".zip":
        return path
    target = path.with_suffix("")
    if target.exists():
        return target
    with tempfile.TemporaryDirectory() as temporary, zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith((".tif", ".tiff"))]
        if not members:
            raise FileNotFoundError(f"no GeoTIFF in {path}")
        archive.extract(members[0], temporary)
        extracted = Path(temporary) / members[0]
        shutil.copy2(extracted, target)
    return target


def _parse_bbox(value: str | None) -> tuple[float, float, float, float] | None:
    """Parse a comma-separated WGS84 bounding box.

    Parameters
    ----------
    value : str or None
        Bounding box text.

    Returns
    -------
    tuple of float or None
        Parsed bounds.

    Raises
    ------
    typer.BadParameter
        When the value does not have four numeric parts.
    """
    if not value:
        return None
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        raise typer.BadParameter("--bbox needs min_lon,min_lat,max_lon,max_lat")
    try:
        return (float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]))
    except ValueError as exc:
        raise typer.BadParameter("--bbox values must be numeric") from exc


def _sources_for_inputs(
    ubc_trees: Path,
    vancouver_trees: Path | None,
    buildings: Path | None,
    boundary: Path | None,
    dem: Path,
    chm: Path | None,
    dsm: Path | None,
) -> tuple[DatasetSource, ...]:
    """Select catalog records for the inputs used by a build.

    Parameters
    ----------
    ubc_trees, vancouver_trees, buildings, boundary, dem, chm, dsm : Path or None
        Build inputs.

    Returns
    -------
    tuple of DatasetSource
        Matching catalog records.
    """
    catalog = load_catalog()
    ids = {"ubc_campus_trees"}
    if vancouver_trees is not None:
        ids.add("vancouver_public_trees")
    if buildings is not None:
        ids.add("ubc_buildings")
    if boundary is not None:
        ids.add("ubc_legal_boundary")
    ids.add("ubc_lidar_2021_dem_1m")
    if chm is not None:
        ids.add("ubc_lidar_2021_chm_1m")
    if dsm is not None:
        ids.add("ubc_lidar_2021_dsm_1m")
    return tuple(catalog.get(source_id) for source_id in sorted(ids))


def _source_payload(source: DatasetSource) -> dict[str, object]:
    """Convert a catalog source to a JSON-safe dictionary.

    Parameters
    ----------
    source : DatasetSource
        Source to convert.

    Returns
    -------
    dict
        Source fields.
    """
    return {
        "source_id": source.source_id,
        "title": source.title,
        "publisher": source.publisher,
        "url": source.url,
        "download_url": source.download_url,
        "filename": source.filename,
        "media_type": source.media_type,
        "licence": source.licence,
        "access_mode": source.access_mode,
        "native_crs": source.native_crs,
        "products": list(source.products),
        "notes": source.notes,
    }


def _point_cloud_payload(summary: PointCloudSummary) -> dict[str, object]:
    """Convert a point-cloud summary to a JSON-safe dictionary.

    Parameters
    ----------
    summary : PointCloudSummary
        Summary to convert.

    Returns
    -------
    dict
        Summary fields.
    """
    return {
        "path": summary.path,
        "point_count": summary.point_count,
        "bounds": list(summary.bounds),
        "crs": summary.crs,
        "class_counts": [list(item) for item in summary.class_counts],
        "density_per_m2": summary.density_per_m2,
        "height_mean_m": summary.height_mean_m,
        "height_p95_m": summary.height_p95_m,
    }


if __name__ == "__main__":
    app()
