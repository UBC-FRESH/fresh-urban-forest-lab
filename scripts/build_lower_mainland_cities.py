#!/usr/bin/env python3
"""Build provisional Surrey, Burnaby, and Coquitlam model instances."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import rasterio
from affine import Affine
from numpy.typing import NDArray
from rasterio.features import MergeAlg, rasterize
from rasterio.warp import Resampling, reproject
from scipy.ndimage import gaussian_filter

from fresh_urban_forest.allometry import is_native_species
from fresh_urban_forest.city_metrics import compute_city_metrics
from fresh_urban_forest.city_off_inventory import detect_city_trees
from fresh_urban_forest.city_pack import build_city_pack
from fresh_urban_forest.inventory import enrich_trees, load_boundary
from fresh_urban_forest.lower_mainland import (
    GridSpec,
    canopy_records_from_classes,
    class_canopy_height,
    class_species,
    grid_for_bounds,
    tree_inventory_summary,
)
from fresh_urban_forest.models import SourceRecord, TreeRecord
from fresh_urban_forest.terrain import RasterData, fill_nan_nearest

ROOT = Path("data/raw/lower_mainland")
LCC = Path("data/tmp/lcc_tif/LCC2020/LCC2020.tif")
CRS = "EPSG:3157"
CITY_CONFIG: dict[str, dict[str, Any]] = {
    "surrey": {
        "dataset_id": "surrey-city-2025",
        "name": "City of Surrey provisional canopy model",
        "out": Path("data/processed/surrey_2025"),
        "res": 5.0,
    },
    "burnaby": {
        "dataset_id": "burnaby-city-2022",
        "name": "City of Burnaby 2022 LiDAR canopy candidates",
        "out": Path("data/processed/burnaby_2022"),
        "res": 2.0,
    },
    "coquitlam": {
        "dataset_id": "coquitlam-city-2025",
        "name": "City of Coquitlam provisional canopy model",
        "out": Path("data/processed/coquitlam_2025"),
        "res": 5.0,
    },
}


def _grid_raster(  # pragma: no cover - operator I/O path
    array: NDArray[np.float32],
    grid: GridSpec,
    path: Path,
    *,
    nodata: float | None = None,
) -> RasterData:
    """Write a projected array and return its raster wrapper."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=grid.height,
        width=grid.width,
        count=1,
        dtype="float32",
        crs=CRS,
        transform=Affine(grid.resolution_m, 0.0, grid.left, 0.0, -grid.resolution_m, grid.top),
        nodata=nodata,
    ) as dataset:
        dataset.write(array.astype("float32"), 1)
    return RasterData(
        path=path,
        crs=CRS,
        transform=Affine(grid.resolution_m, 0.0, grid.left, 0.0, -grid.resolution_m, grid.top),
        bounds=grid.bounds,
        array=array.astype(np.float32),
        cell_area_m2=grid.resolution_m * grid.resolution_m,
    )


def _boundary_grid(  # pragma: no cover - operator I/O path
    path: Path,
    resolution_m: float,
) -> tuple[gpd.GeoDataFrame, GridSpec]:
    """Load a boundary and build a projected grid over it."""
    frame = gpd.read_file(path).to_crs(CRS)
    if frame.empty:
        raise RuntimeError(f"empty boundary: {path}")
    return (
        frame,
        grid_for_bounds(
            (
                float(frame.total_bounds[0]),
                float(frame.total_bounds[1]),
                float(frame.total_bounds[2]),
                float(frame.total_bounds[3]),
            ),
            resolution_m=resolution_m,
        ),
    )


def _boundary_raster(  # pragma: no cover - operator I/O path
    frame: gpd.GeoDataFrame,
    grid: GridSpec,
) -> NDArray[np.uint8]:
    """Rasterize a boundary to a boolean mask."""
    transform = Affine(grid.resolution_m, 0.0, grid.left, 0.0, -grid.resolution_m, grid.top)
    return np.asarray(
        rasterize(
            [(geom, 1) for geom in frame.geometry if geom is not None],
            out_shape=(grid.height, grid.width),
            transform=transform,
            fill=0,
            dtype="uint8",
        ),
        dtype=np.uint8,
    )


def _lcc_grid(  # pragma: no cover - operator I/O path
    frame: gpd.GeoDataFrame,
    grid: GridSpec,
) -> NDArray[np.uint8]:
    """Reproject the Metro LCC 2020 raster onto a city grid."""
    with rasterio.open(LCC) as source:
        destination = np.zeros((grid.height, grid.width), dtype=np.uint8)
        reproject(
            source=rasterio.band(source, 1),
            destination=destination,
            src_transform=source.transform,
            src_crs=source.crs,
            src_nodata=0,
            dst_transform=Affine(
                grid.resolution_m, 0.0, grid.left, 0.0, -grid.resolution_m, grid.top
            ),
            dst_crs=CRS,
            dst_nodata=0,
            resampling=Resampling.nearest,
        )
    return destination


def _contour_dem(  # pragma: no cover - operator I/O path
    frame: gpd.GeoDataFrame,
    grid: GridSpec,
    contour_path: Path,
    path: Path,
) -> RasterData:
    """Build a provisional DEM by rasterizing contour vertices."""
    contour_frame = gpd.read_file(contour_path).to_crs(CRS)
    elevation_values = []
    sums = np.zeros((grid.height, grid.width), dtype=np.float64)
    counts = np.zeros((grid.height, grid.width), dtype=np.uint16)
    for geometry, elevation in zip(
        contour_frame.geometry,
        contour_frame["ELEVATION"],
        strict=True,
    ):
        if geometry is None or not np.isfinite(float(elevation)):
            continue
        lines = [geometry] if geometry.geom_type == "LineString" else list(geometry.geoms)
        for line in lines:
            coords = np.asarray(line.coords, dtype=np.float64)
            if len(coords) < 2:
                continue
            cols = np.floor((coords[:, 0] - grid.left) / grid.resolution_m).astype(int)
            rows = np.floor((grid.top - coords[:, 1]) / grid.resolution_m).astype(int)
            valid = (cols >= 0) & (cols < grid.width) & (rows >= 0) & (rows < grid.height)
            if not np.any(valid):
                continue
            np.add.at(sums, (rows[valid], cols[valid]), float(elevation))
            np.add.at(counts, (rows[valid], cols[valid]), 1)
            elevation_values.append(float(elevation))
    dem = np.full(sums.shape, np.nan, dtype=np.float32)
    mask = counts > 0
    dem[mask] = (sums[mask] / counts[mask]).astype(np.float32)
    if not np.any(np.isfinite(dem)):
        raise RuntimeError(f"no contour elevations in {contour_path}")
    dem = fill_nan_nearest(dem).astype(np.float32)
    dem = gaussian_filter(dem, sigma=1.0).astype(np.float32)
    return _grid_raster(dem, grid, path, nodata=np.nan)


def _lcc_chm(  # pragma: no cover - operator I/O path
    classes: NDArray[np.uint8],
    grid: GridSpec,
    path: Path,
) -> RasterData:
    """Build a screening CHM from land-cover classes."""
    heights = np.zeros(classes.shape, dtype=np.float32)
    for code in np.unique(classes):
        heights[classes == int(code)] = class_canopy_height(int(code))
    heights[~np.isin(classes, [6, 7, 8, 15, 16])] = 0.0
    return _grid_raster(heights, grid, path, nodata=np.nan)


def _building_rasters(  # pragma: no cover - operator I/O path
    buildings: gpd.GeoDataFrame,
    grid: GridSpec,
    mask_path: Path,
    height_path: Path,
) -> tuple[RasterData, NDArray[np.uint8]]:
    """Rasterize building masks and building heights."""
    transform = Affine(grid.resolution_m, 0.0, grid.left, 0.0, -grid.resolution_m, grid.top)
    mask = np.asarray(
        rasterize(
            [(geom, 1) for geom in buildings.geometry if geom is not None],
            out_shape=(grid.height, grid.width),
            transform=transform,
            fill=0,
            dtype="uint8",
        ),
        dtype=np.uint8,
    )
    heights = rasterize(
        [
            (geom, float(height))
            for geom, height in zip(buildings.geometry, buildings["height"], strict=True)
            if geom is not None
        ],
        out_shape=(grid.height, grid.width),
        transform=transform,
        fill=0,
        dtype="float32",
        merge_alg=MergeAlg.replace,
    )
    with rasterio.open(
        mask_path,
        "w",
        driver="GTiff",
        height=grid.height,
        width=grid.width,
        count=1,
        dtype="uint8",
        crs=CRS,
        transform=transform,
    ) as dataset:
        dataset.write(mask, 1)
    return _grid_raster(heights, grid, height_path, nodata=0.0), mask


def _write_mask(  # pragma: no cover - operator I/O path
    mask: NDArray[np.uint8],
    grid: GridSpec,
    path: Path,
) -> None:
    """Write a uint8 mask raster."""
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=grid.height,
        width=grid.width,
        count=1,
        dtype="uint8",
        crs=CRS,
        transform=Affine(grid.resolution_m, 0.0, grid.left, 0.0, -grid.resolution_m, grid.top),
    ) as dataset:
        dataset.write(mask, 1)


def _water_mask(  # pragma: no cover - operator I/O path
    classes: NDArray[np.uint8],
    grid: GridSpec,
    path: Path,
) -> NDArray[np.uint8]:
    """Write an LCC water mask."""
    water = np.asarray(classes == 12, dtype=np.uint8)
    _write_mask(water, grid, path)
    return water


def _sources(  # pragma: no cover - operator I/O path
    city: str,
    generated: str,
) -> tuple[SourceRecord, ...]:
    """Build source records for one city instance."""
    common = (
        SourceRecord(
            source_id="metro_lcc_2020",
            title="Metro Vancouver Land Cover Classification 2020",
            publisher="Metro Vancouver",
            url="https://open-data-portal-metrovancouver.hub.arcgis.com/",
            licence="Open Government Licence - Metro Vancouver",
            access_mode="direct_http",
            retrieved_utc=generated,
            notes=(
                "5 m hybrid land-cover classification; class labels are context, not species IDs."
            ),
        ),
        SourceRecord(
            source_id="osm_roads",
            title="OpenStreetMap road centrelines",
            publisher="OpenStreetMap contributors",
            url="https://www.openstreetmap.org/copyright",
            licence="ODbL 1.0",
            access_mode="overpass_api",
            retrieved_utc=generated,
            notes="Pale street underlay and 3D road overlay.",
        ),
    )
    if city == "surrey":
        local: tuple[SourceRecord, ...] = (
            SourceRecord(
                source_id="surrey_trees",
                title="City of Surrey Trees",
                publisher="City of Surrey",
                url="https://opendata-surrey.hub.arcgis.com/",
                licence="Open Government Licence - Surrey",
                access_mode="arcgis_rest",
                retrieved_utc=generated,
                notes=(
                    "100,969 public street/park tree points; height and DBH are not "
                    "published in this service."
                ),
            ),
            SourceRecord(
                source_id="surrey_buildings",
                title="City of Surrey Building Footprints",
                publisher="City of Surrey",
                url="https://opendata-surrey.hub.arcgis.com/",
                licence="Open Government Licence - Surrey",
                access_mode="arcgis_rest",
                retrieved_utc=generated,
                notes="Building footprints with building height and ground elevation.",
            ),
            SourceRecord(
                source_id="surrey_contours",
                title="City of Surrey 5 m contours",
                publisher="City of Surrey",
                url="https://opendata-surrey.hub.arcgis.com/",
                licence="Open Government Licence - Surrey",
                access_mode="arcgis_rest",
                retrieved_utc=generated,
                notes="Provisional terrain surface.",
            ),
        )
        return (*local, *common)
    if city == "burnaby":
        local = (
            SourceRecord(
                source_id="burnaby_lidar",
                title="City of Burnaby 2022 LiDAR DEM/DSM",
                publisher="City of Burnaby",
                url="https://data.burnaby.ca/",
                licence="Open Government Licence - Burnaby",
                access_mode="direct_http",
                retrieved_utc=generated,
                notes="2022 0.5 m DEM and DSM; CHM = DSM - DEM.",
            ),
            SourceRecord(
                source_id="burnaby_buildings",
                title="City of Burnaby Building Outlines",
                publisher="City of Burnaby",
                url="https://data.burnaby.ca/",
                licence="Open Government Licence - Burnaby",
                access_mode="arcgis_rest",
                retrieved_utc=generated,
                notes="Building heights from the city outline field.",
            ),
        )
        return (*local, *common)
    local = (
        SourceRecord(
            source_id="coquitlam_buildings",
            title="City of Coquitlam Buildings",
            publisher="City of Coquitlam",
            url="https://data.coquitlam.ca/",
            licence="Open Government Licence - Coquitlam",
            access_mode="arcgis_rest",
            retrieved_utc=generated,
            notes="Building footprints with height.",
        ),
        SourceRecord(
            source_id="coquitlam_contours",
            title="City of Coquitlam 2023 contours",
            publisher="City of Coquitlam",
            url="https://data.coquitlam.ca/",
            licence="Open Government Licence - Coquitlam",
            access_mode="arcgis_rest",
            retrieved_utc=generated,
            notes=("Provisional terrain surface; canonical LiDAR is pending delivery."),
        ),
    )
    return (*local, *common)


def _surrey_trees(  # pragma: no cover - operator I/O path
    path: Path,
    dem: RasterData,
    chm: RasterData,
) -> tuple[tuple[TreeRecord, ...], int]:
    """Load and enrich the Surrey public tree inventory."""
    frame = gpd.read_file(path).to_crs(4326)
    records: list[TreeRecord] = []
    for _, row in frame.iterrows():
        geometry = row.geometry
        if geometry is None or geometry.is_empty:
            continue
        taxa = str(row.get("Taxonomy") or "").strip()
        if not taxa:
            taxa = " ".join(
                str(value).strip()
                for value in (row.get("TREE_GENUS"), row.get("TREE_SPECIES"))
                if value
            )
        tree_id = str(row.get("OBJECTID") or len(records))
        records.append(
            TreeRecord(
                tree_id=f"surrey:{tree_id}",
                lon=float(geometry.x),
                lat=float(geometry.y),
                species=taxa,
                common_name=str(row.get("DESCRIPTION") or ""),
                genus=str(row.get("TREE_GENUS") or ""),
                status="alive",
                source="surrey_trees",
                source_date=None,
                native=is_native_species(taxa),
                attributes={
                    "park": str(row.get("PARK") or ""),
                    "tree_type": str(row.get("TREE_TYPE") or ""),
                    "height_measured": "false",
                    "dbh_measured": "false",
                    "crown_width_measured": "false",
                },
            )
        )
    enriched = enrich_trees(tuple(records), dem, chm)
    return tuple(enriched), len(records)


def _burnaby_trees(  # pragma: no cover - operator I/O path
    chm_path: Path,
    lcc_classes: NDArray[np.uint8],
    lcc_grid: GridSpec,
    dem: RasterData,
    chm: RasterData,
) -> tuple[tuple[TreeRecord, ...], int]:
    """Detect Burnaby crowns from the CHM and attach land-cover context."""
    detected = detect_city_trees(chm_path, resolution_m=1.0, tile_m=1000.0, buffer_m=40.0)
    records: list[TreeRecord] = []
    for crown in detected:
        if crown.height_m > 50.0:
            continue
        col = int((crown.x - lcc_grid.left) / lcc_grid.resolution_m)
        row = int((lcc_grid.top - crown.y) / lcc_grid.resolution_m)
        if 0 <= row < lcc_classes.shape[0] and 0 <= col < lcc_classes.shape[1]:
            code = int(lcc_classes[row, col])
        else:
            code = 0
        label = class_species(code)
        group = "unknown"
        if code in {6, 15}:
            group = "conifer"
        elif code in {7, 16}:
            group = "deciduous"
        records.append(
            TreeRecord(
                tree_id=f"burnaby:{crown.tree_id}",
                lon=crown.lon,
                lat=crown.lat,
                species=label,
                common_name="LiDAR candidate",
                genus="",
                height_m=crown.height_m,
                crown_width_m=crown.crown_radius_m * 2.0,
                crown_ratio=0.55,
                status="alive",
                source="burnaby_lidar_2022",
                source_date="2022",
                native=None,
                x_m=crown.x,
                y_m=crown.y,
                attributes={
                    "height_measured": "false",
                    "crown_width_measured": "false",
                    "species_measured": "false",
                    "land_cover_group": group,
                    "candidate": "true",
                },
            )
        )
    enriched = enrich_trees(tuple(records), dem, chm)
    return tuple(enriched), len(records)


def _build_city(city: str) -> None:  # pragma: no cover - operator I/O path
    """Compile one city instance."""
    config = CITY_CONFIG[city]
    out = config["out"]
    out.mkdir(parents=True, exist_ok=True)
    root = ROOT / city
    boundary_frame, grid = _boundary_grid(root / "boundary.geojson", float(config["res"]))
    boundary = load_boundary(root / "boundary.geojson")
    buildings = gpd.read_file(root / "buildings.geojson").to_crs(CRS)
    classes = _lcc_grid(boundary_frame, grid)
    (out / "aoi.geojson").write_text(
        boundary_frame.assign(name=f"{city.title()} boundary").to_crs(4326).to_json(),
        encoding="utf-8",
    )
    building_height, building_mask = _building_rasters(
        buildings,
        grid,
        out / "_building_mask.tif",
        out / "_building_height.tif",
    )
    water_mask = _water_mask(classes, grid, out / "_water_mask.tif")
    generated = dt.datetime.now(dt.UTC).isoformat()
    if city == "burnaby":
        dem, chm = _burnaby_dem_chm(boundary_frame, grid, root)
        building_mask = np.maximum(building_mask, np.asarray(classes == 1, dtype=np.uint8))
        _write_mask(building_mask, grid, out / "_building_mask.tif")
        excluded = building_mask.astype(bool) | water_mask.astype(bool)
        chm = _grid_raster(
            np.where(excluded, np.nan, chm.array).astype(np.float32),
            grid,
            out / "_chm.tif",
            nodata=np.nan,
        )
        _grid_raster(dem.array, grid, out / "_dem.tif", nodata=np.nan)
        trees, source_rows = _burnaby_trees(out / "_chm.tif", classes, grid, dem, chm)
    else:
        dem = _contour_dem(boundary_frame, grid, root / "contours_raw.geojson", out / "_dem.tif")
        chm = _lcc_chm(classes, grid, out / "_chm.tif")
        if city == "surrey":
            trees, source_rows = _surrey_trees(root / "trees_raw.geojson", dem, chm)
        else:
            trees = canopy_records_from_classes(classes, grid, step_m=20.0)
            trees = enrich_trees(trees, dem, chm)
            source_rows = len(trees)
    caveats = {
        "surrey": (
            "Surrey tree heights and DBH are imputed; the public tree service does not "
            "publish measured height or diameter.",
            "Canopy cover comes from the Metro 2020 land-cover tree classes, not a Surrey "
            "2022 canopy-height model.",
            "This is a provisional public-data compilation, not an urban forest census.",
        ),
        "burnaby": (
            "Tree records are CHM-derived candidates, not a public-tree inventory.",
            "Conifer/deciduous labels come from Metro 2020 land cover, not field species.",
            "Canopy cover and volume come from the 2022 Burnaby DEM/DSM.",
            "This is a screening candidate layer, not a census.",
        ),
        "coquitlam": (
            "Tree records are land-cover canopy candidates, not individual-tree observations.",
            "Canonical Coquitlam LiDAR/imagery is pending delivery.",
            "Heights are class assumptions from Metro 2020 land cover.",
            "This is a provisional public-data compilation, not a census.",
        ),
    }[city]
    city_metrics = compute_city_metrics(
        trees,
        chm_path=out / "_chm.tif",
        building_mask_path=out / "_building_mask.tif",
        water_mask_path=out / "_water_mask.tif",
        aoi_path=out / "aoi.geojson",
        out_dir=out,
        city_name=city.title(),
        published_canopy_cover_pct=None,
        caveats=caveats,
        tree_record_label={
            "surrey": "Public tree records",
            "burnaby": "LiDAR candidates",
            "coquitlam": "Canopy candidates",
        }[city],
        canopy_source_label={
            "surrey": "land-cover height field",
            "burnaby": "2022 LiDAR height field",
            "coquitlam": "land-cover height field",
        }[city],
    )
    inventory_summary = tree_inventory_summary(trees, source_rows=source_rows)
    build_city_pack(
        trees=trees,
        city_metrics=city_metrics,
        inventory_summary=inventory_summary,
        dem=dem,
        chm=chm,
        building_footprints=root / "buildings.geojson",
        building_height=building_height,
        boundary=boundary,
        sources=_sources(city, generated),
        out_dir=out,
        dataset_id=str(config["dataset_id"]),
        name=str(config["name"]),
        max_trees=30_000,
        max_buildings=12_000,
        generated_utc=generated,
    )
    print(f"{city}: {len(trees)} trees, slope terrain, output {out}", flush=True)


def _burnaby_dem_chm(  # pragma: no cover - operator I/O path
    boundary_frame: gpd.GeoDataFrame,
    grid: GridSpec,
    root: Path,
) -> tuple[RasterData, RasterData]:
    """Read Burnaby 0.5 m DEM/DSM and resample to the city grid."""
    paths = {
        "dem": root / "extracted" / "DEM_bby.tif",
        "dsm": root / "extracted" / "DSM_bby.tif",
    }
    arrays: dict[str, NDArray[np.float32]] = {}
    for key, path in paths.items():
        with rasterio.open(path) as dataset:
            output = np.full((grid.height, grid.width), np.nan, dtype=np.float32)
            reproject(
                source=rasterio.band(dataset, 1),
                destination=output,
                src_transform=dataset.transform,
                src_crs=dataset.crs,
                dst_transform=Affine(
                    grid.resolution_m, 0.0, grid.left, 0.0, -grid.resolution_m, grid.top
                ),
                dst_crs=CRS,
                resampling=Resampling.average,
            )
            arrays[key] = output
    chm = arrays["dsm"] - arrays["dem"]
    chm[chm < 0.2] = np.nan
    boundary_mask = _boundary_raster(boundary_frame, grid).astype(bool)
    dem = np.where(boundary_mask, arrays["dem"], np.nan).astype(np.float32)
    chm = np.where(boundary_mask, chm, np.nan).astype(np.float32)
    return (
        _grid_raster(dem, grid, root / "_dem_source.tif", nodata=np.nan),
        _grid_raster(chm, grid, root / "_chm_source.tif", nodata=np.nan),
    )


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - operator I/O path
    """Run the P34 city build.

    Parameters
    ----------
    argv : list of str or None
        Command-line arguments.

    Returns
    -------
    int
        Process status.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", choices=("surrey", "burnaby", "coquitlam", "all"), default="all")
    args = parser.parse_args(argv)
    cities = tuple(CITY_CONFIG) if args.city == "all" else (args.city,)
    for city in cities:
        _build_city(city)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
