"""Tests for raster sampling, inventory normalisation, change, and tree detection."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from rasterio.transform import from_origin

from fresh_urban_forest.change import canopy_change, change_grid
from fresh_urban_forest.inventory import (
    enrich_trees,
    load_boundary,
    load_buildings,
    load_ubc_trees,
    load_vancouver_trees,
)
from fresh_urban_forest.itd import detect_trees, detected_trees_geojson
from fresh_urban_forest.terrain import (
    build_terrain_grid,
    canopy_cover_pct,
    canopy_volume_m3,
    crop_raster,
    height_percentiles,
    project_lonlat,
    read_raster,
    sample_raster,
    sample_raster_lonlat,
    sample_terrain_grid,
    slope_percent,
    unproject_xy,
)
from tests.fixtures import CRS, make_raster, make_trees


def test_project_and_unproject_round_trip() -> None:
    """A WGS84 coordinate survives a round trip through EPSG:3157."""
    x, y = project_lonlat(-123.25, 49.26, CRS)
    lon, lat = unproject_xy(x, y, CRS)
    assert lon == pytest.approx(-123.25, abs=1e-6)
    assert lat == pytest.approx(49.26, abs=1e-6)


def test_read_raster_masks_nodata(tmp_path: Path) -> None:
    """Raster nodata becomes NaN and the cell area is calculated."""
    import rasterio

    path = tmp_path / "values.tif"
    values = np.array([[1.0, -9999.0], [3.0, 4.0]], dtype=np.float32)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=2,
        width=2,
        count=1,
        dtype="float32",
        crs=CRS,
        transform=from_origin(0, 2, 1, 1),
        nodata=-9999.0,
    ) as dataset:
        dataset.write(values, 1)
    raster = read_raster(path)
    assert np.isnan(raster.array[0, 1])
    assert raster.cell_area_m2 == 1.0


def test_sample_raster_and_grid(tmp_path: Path) -> None:
    """Raster and terrain sampling return the expected cells."""
    values = np.arange(100, dtype=np.float32).reshape(10, 10)
    raster = make_raster(tmp_path / "grid.tif", values)
    sampled = sample_raster(raster, np.array([5.0, -100.0]), np.array([95.0, 50.0]))
    assert sampled[0] == values[0, 0]
    assert np.isnan(sampled[1])
    lon, lat = unproject_xy(5.0, 95.0, CRS)
    assert sample_raster_lonlat(raster, np.array([lon]), np.array([lat]))[0] == values[0, 0]
    grid = build_terrain_grid(raster, raster, max_size=5)
    elevation, canopy, slope = sample_terrain_grid(grid, *unproject_xy(50.0, 50.0, CRS))
    assert elevation >= 0.0
    assert canopy >= 0.0
    assert slope >= 0.0


def test_crop_raster_to_bounds(tmp_path: Path) -> None:
    """A raster crop keeps the requested projected window."""
    values = np.arange(100, dtype=np.float32).reshape(10, 10)
    raster = make_raster(tmp_path / "grid.tif", values)
    cropped = crop_raster(raster, (20.0, 20.0, 70.0, 70.0))
    assert cropped.array.shape == (5, 5)
    assert cropped.bounds == (20.0, 20.0, 70.0, 70.0)
    assert cropped.array[0, 0] == values[3, 2]


def test_canopy_summary_functions() -> None:
    """Cover, volume, and percentiles use valid cells only."""
    chm = np.array([[0.0, 1.0, 5.0], [10.0, np.nan, 20.0]], dtype=np.float32)
    assert canopy_cover_pct(chm, threshold_m=2.0) == pytest.approx(60.0)
    assert canopy_volume_m3(chm, cell_area_m2=2.0) == pytest.approx(72.0)
    summary = height_percentiles(chm)
    assert summary["max"] == 20.0
    assert summary["p95"] > 0
    empty = height_percentiles(np.zeros((2, 2), dtype=np.float32))
    assert empty["mean"] == 0.0
    grid = make_raster(Path("x.tif"), np.zeros((3, 3), dtype=np.float32))
    terrain = build_terrain_grid(grid, None, max_size=3)
    assert slope_percent(terrain).shape == (3, 3)


def test_load_ubc_geojson_and_csv(tmp_path: Path) -> None:
    """UBC GeoJSON and CSV snapshots normalise to tree records."""
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-123.25, 49.26]},
                "properties": {
                    "TREEID": "1",
                    "TAXA": "Thuja plicata",
                    "COMMON_NAME": "Western red cedar",
                    "DBH": 34.5,
                    "THEIGHT": 18.0,
                    "CROWNWIDTH1": 6.0,
                    "CROWNWIDTH2": 8.0,
                    "NATIVE_TREE": "Y",
                    "TREE_STATUS": "alive",
                    "DATE_MEASURE": "2024",
                },
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-123.24, 49.25]},
                "properties": {"TREEID": "2", "TAXA": "Acer rubrum"},
            },
        ],
    }
    path = tmp_path / "trees.geojson"
    path.write_text(json.dumps(geojson), encoding="utf-8")
    trees = load_ubc_trees(path)
    assert len(trees) == 2
    assert trees[0].tree_id == "ubc:1"
    assert trees[0].crown_width_m == 7.0
    assert trees[0].native is True
    filtered = load_ubc_trees(path, bbox=(-123.255, 49.255, -123.245, 49.265))
    assert len(filtered) == 1
    csv_path = tmp_path / "trees.csv"
    csv_path.write_text(
        "LONG,LAT,TREEID,TAXA,DBH,THEIGHT,CROWNWIDTH1,NATIVE_TREE\n"
        "-123.25,49.26,3,Acer rubrum,20,10,4,N\n",
        encoding="utf-8",
    )
    assert load_ubc_trees(csv_path)[0].tree_id == "ubc:3"


def test_load_vancouver_trees(tmp_path: Path) -> None:
    """Vancouver CSV fields map to the shared tree contract."""
    path = tmp_path / "vancouver.csv"
    path.write_text(
        "asset_id,address,common_name,genus_name,species_name,cultivar_name,height_m,"
        "diameter_cm,local_area,geom,geo_point_2d\n"
        "1,1 Main St,Red maple,ACER,RUBRUM,NONE,12.5,30.0,Kitsilano,"
        '"{""coordinates"": [-123.25, 49.26], ""type"": ""Point""}",'
        '"49.26, -123.25"\n',
        encoding="utf-8",
    )
    trees = load_vancouver_trees(path)
    assert len(trees) == 1
    assert trees[0].tree_id == "vancouver:1"
    assert trees[0].species == "ACER RUBRUM"
    assert trees[0].dbh_cm == 30.0
    assert load_vancouver_trees(path, bbox=(-123.20, 49.20, -123.10, 49.30)) == []


def test_load_buildings_and_boundary(tmp_path: Path) -> None:
    """Building footprints and boundary rings survive a GeoJSON read."""
    building = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"BLDG_UID": "b1", "NAME": "Hall", "BLDG_HEIGHT": 19.0},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[-123.25, 49.26], [-123.249, 49.26], [-123.249, 49.261], [-123.25, 49.26]]
                    ],
                },
            }
        ],
    }
    building_path = tmp_path / "buildings.geojson"
    building_path.write_text(json.dumps(building), encoding="utf-8")
    buildings = load_buildings(building_path)
    assert buildings[0].building_id == "b1"
    assert buildings[0].height_m == 19.0
    boundary_path = tmp_path / "boundary.geojson"
    boundary_path.write_text(json.dumps(building), encoding="utf-8")
    boundary = load_boundary(boundary_path)
    assert len(boundary) == 4
    empty_path = tmp_path / "empty.geojson"
    empty_path.write_text('{"type": "FeatureCollection", "features": []}', encoding="utf-8")
    assert load_boundary(empty_path) == ()


def test_enrich_trees_imputes_missing_dimensions(tmp_path: Path) -> None:
    """Missing height, diameter, and crown width are filled from the DEM and CHM."""
    dem = make_raster(tmp_path / "dem.tif", np.zeros((10, 10), dtype=np.float32))
    chm = make_raster(tmp_path / "chm.tif", np.full((10, 10), 9.0, dtype=np.float32))
    trees = make_trees(3)
    enriched = enrich_trees(trees, dem, chm)
    assert all(tree.x_m is not None and tree.y_m is not None for tree in enriched)
    assert enriched[0].height_m is not None
    assert enriched[0].height_m > 0
    assert enriched[0].dbh_cm is not None
    assert enriched[0].dbh_cm > 0
    assert enriched[0].lidar_height_m == 9.0
    assert enrich_trees([], dem, chm) == ()


def test_fill_nan_nearest_removes_render_holes() -> None:
    """Missing terrain cells are filled from their nearest valid neighbour."""
    from fresh_urban_forest.terrain import fill_nan_nearest

    values = np.asarray([[np.nan, 10.0], [20.0, np.nan]], dtype=np.float64)
    filled = fill_nan_nearest(values)
    assert np.isfinite(filled).all()
    assert filled[0, 0] in {10.0, 20.0}
    assert filled[1, 1] in {10.0, 20.0}
    all_missing = fill_nan_nearest(np.full((2, 2), np.nan, dtype=np.float64))
    assert np.isfinite(all_missing).all()


def test_detect_trees_and_change(tmp_path: Path) -> None:
    """Local maxima and watershed detection find planted crowns, and change is additive."""
    chm = np.zeros((30, 30), dtype=np.float32)
    chm[5:12, 5:12] = 18.0
    chm[18:24, 18:24] = 12.0
    raster = make_raster(tmp_path / "chm.tif", chm)
    grid = build_terrain_grid(raster, raster, max_size=30)
    detected = detect_trees(grid, min_height_m=3.0, window_m=4.0)
    assert len(detected) >= 2
    assert detected[0].height_m >= detected[1].height_m
    payload = detected_trees_geojson(detected)
    assert payload["type"] == "FeatureCollection"
    features = payload["features"]
    assert isinstance(features, list)
    assert len(features) == len(detected)
    with pytest.raises(ValueError, match="canopy_height"):
        detect_trees(build_terrain_grid(raster, None), min_height_m=3.0)
    change = canopy_change(chm, chm, threshold_m=2.0)
    assert change.gain_m2 == 0.0
    assert change.loss_m2 == 0.0
    gain = np.zeros_like(chm)
    gain[1:4, 1:4] = 5.0
    changed = canopy_change(chm, gain, threshold_m=2.0)
    assert changed.loss_m2 > 0
    grid_change = change_grid(chm, gain, threshold_m=2.0)
    assert grid_change.shape == chm.shape
    assert set(np.unique(grid_change)).issubset({-1, 0, 1})
    with pytest.raises(ValueError, match="share a shape"):
        canopy_change(chm, chm[:-1, :-1])
    with pytest.raises(ValueError, match="share a shape"):
        change_grid(chm, chm[:-1, :-1])
