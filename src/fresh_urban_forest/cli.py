"""Command-line interface for the urban-forest lab.

The CLI is the reproducible path: catalog search, source materialization, dataset build,
dataset inspection, and the local web service. The browser is a view over the same typed
commands, not a separate implementation.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from dataclasses import asdict
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from fresh_urban_forest.catalog import DatasetSource, load_catalog
from fresh_urban_forest.change import canopy_change
from fresh_urban_forest.dataset import build_dataset, dataset_summary, load_dataset
from fresh_urban_forest.inventory import (
    load_boundary,
    load_buildings,
    load_ubc_trees,
    load_vancouver_trees,
)
from fresh_urban_forest.itd import detect_trees, detected_trees_geojson
from fresh_urban_forest.lidar import PointCloudSummary, canopies_from_pair, summarize_point_cloud
from fresh_urban_forest.materialize import materialize_sources, read_materialization_manifest
from fresh_urban_forest.terrain import RasterData, read_raster

app = typer.Typer(help="Open urban-forest LiDAR, inventory, growth, and 3-D decision support.")
catalog_app = typer.Typer(help="Inspect and materialize public data sources.")
app.add_typer(catalog_app, name="catalog")
console = Console()

DEST_OPTION = typer.Option(..., "--dest", help="Destination directory.")
OUT_OPTION = typer.Option(..., "--out", help="Output dataset directory.")
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
THRESHOLD_OPTION = typer.Option(2.0, "--threshold", help="Canopy threshold in metres.")


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
    )
    uvicorn.run(app_instance, host=host, port=port)


@app.command("detect-trees")
def detect_trees_command(
    dataset: Path = DATASET_OPTION,
    out: Path = OUT_OPTION,
    min_height: float = MIN_HEIGHT_OPTION,
    window: float = WINDOW_OPTION,
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
    """
    loaded = load_dataset(dataset)
    trees = detect_trees(loaded.terrain, min_height_m=min_height, window_m=window)
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
