"""Tests for raster shade and the 400 m shade/equity screen."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import cast

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import box

from fresh_urban_forest.heat_priority import (
    PRIORITY_EVIDENCE,
    SHADE_EVIDENCE,
    RasterShade,
    build_priority_grid,
    building_height_raster,
    priority_geojson,
    priority_png,
    raster_shade,
    write_priority_product,
)
from fresh_urban_forest.models import Building

CRS = "EPSG:3157"
BOUNDS = (493_000.0, 5_455_000.0, 493_200.0, 5_455_200.0)
ZONE = dt.timezone(dt.timedelta(hours=-7))


def _when(hour: int = 12) -> tuple[dt.datetime, ...]:
    """Return one local summer solar sample."""
    return (dt.datetime(2026, 6, 21, hour, tzinfo=ZONE),)


def test_raster_shade_casts_tree_shadow_north_of_canopy() -> None:
    """At midday the shadow falls north, not south, of a tall crown."""
    shape = (40, 40)
    dem = np.zeros(shape, dtype=np.float64)
    canopy = np.zeros(shape, dtype=np.float64)
    canopy[20, 20] = 25.0
    building = np.zeros(shape, dtype=np.float64)
    shade = raster_shade(
        dem=dem,
        canopy_height=canopy,
        building_height=building,
        bounds=BOUNDS,
        crs=CRS,
        whens=_when(13),
        max_distance_m=30.0,
        step_m=5.0,
    )
    assert shade.tree_shade_fraction[19, 20] > 0.0
    assert shade.tree_shade_fraction[22, 20] == 0.0
    assert shade.metrics["tree_shade_fraction"] > 0.0
    assert shade.metrics["sunlit_fraction"] < 1.0


def test_raster_shade_casts_building_shadow() -> None:
    """A building contributes a separate building-shade fraction."""
    shape = (40, 40)
    dem = np.zeros(shape, dtype=np.float64)
    canopy = np.zeros(shape, dtype=np.float64)
    building = np.zeros(shape, dtype=np.float64)
    building[20, 20] = 30.0
    shade = raster_shade(
        dem=dem,
        canopy_height=canopy,
        building_height=building,
        bounds=BOUNDS,
        crs=CRS,
        whens=_when(13),
        max_distance_m=30.0,
        step_m=5.0,
    )
    assert shade.building_shade_fraction[19, 20] > 0.0
    assert shade.metrics["building_shade_fraction"] > 0.0


def test_raster_shade_rejects_bad_inputs() -> None:
    """Shape, bounds, and sampling errors are explicit."""
    arrays = (np.zeros((4, 4)), np.zeros((4, 4)), np.zeros((4, 4)))
    with pytest.raises(ValueError, match="share a 2-D shape"):
        raster_shade(
            dem=arrays[0],
            canopy_height=np.zeros((5, 4)),
            building_height=arrays[2],
            bounds=BOUNDS,
            crs=CRS,
            whens=_when(),
        )
    with pytest.raises(ValueError, match="positive width"):
        raster_shade(
            dem=arrays[0],
            canopy_height=arrays[1],
            building_height=arrays[2],
            bounds=(0.0, 0.0, 0.0, 1.0),
            crs=CRS,
            whens=_when(),
        )
    with pytest.raises(ValueError, match="at least one solar sample"):
        raster_shade(
            dem=arrays[0],
            canopy_height=arrays[1],
            building_height=arrays[2],
            bounds=BOUNDS,
            crs=CRS,
            whens=(),
        )


def test_building_height_raster_projects_a_footprint() -> None:
    """A building height is rasterised at its projected footprint."""
    shape = (40, 40)
    building = Building(
        building_id="b1",
        name="Test",
        height_m=12.0,
        rings=(
            (
                (-123.0950, 49.2484),
                (-123.0946, 49.2484),
                (-123.0946, 49.2488),
                (-123.0950, 49.2488),
            ),
        ),
    )
    heights = building_height_raster((building,), bounds=BOUNDS, shape=shape, crs=CRS)
    assert float(np.max(heights)) > 0.0


def _shade_fixture(shape: tuple[int, int]) -> RasterShade:
    """Build a two-half shade fixture with a known east-west contrast."""
    _rows, cols = shape
    tree = np.zeros(shape, dtype=np.float32)
    combined = np.zeros(shape, dtype=np.float32)
    tree[:, cols // 2 :] = 0.8
    combined[:, cols // 2 :] = 0.8
    return RasterShade(
        whens=_when(),
        step_hours=1.0,
        target_height_m=1.5,
        tree_shade_fraction=tree,
        building_shade_fraction=np.zeros(shape, dtype=np.float32),
        combined_shade_fraction=combined,
        sunlit_fraction=(1.0 - combined).astype(np.float32),
        metrics={"combined_shade_fraction": float(combined.mean())},
        evidence=SHADE_EVIDENCE,
    )


def test_build_priority_grid_uses_population_weighted_equity() -> None:
    """The west cell is high need and the east cell is low need."""
    shape = (40, 40)
    shade = _shade_fixture(shape)
    canopy = np.full(shape, 10.0, dtype=np.float64)
    equity = gpd.GeoDataFrame(
        {
            "DGUID": ["west", "east"],
            "population": [500.0, 500.0],
            "equity_score": [0.9, 0.1],
        },
        geometry=[box(0, 0, 200, 400), box(200, 0, 400, 400)],
        crs=CRS,
    )
    cells = build_priority_grid(
        shade,
        bounds=(0.0, 0.0, 400.0, 400.0),
        crs=CRS,
        canopy_height=canopy,
        equity=equity,
        cell_size_m=200.0,
    )
    assert len(cells) == 4
    west = [cell for cell in cells if cell.col == 0]
    east = [cell for cell in cells if cell.col == 1]
    assert all(cell.equity_score == pytest.approx(0.9) for cell in west)
    assert all(cell.equity_score == pytest.approx(0.1) for cell in east)
    assert all(cell.shade_deficit == pytest.approx(1.0) for cell in west)
    assert all(cell.shade_deficit == pytest.approx(0.2) for cell in east)
    assert all(cell.shade_efficiency_m2h_per_m3 > 0.0 for cell in east)
    assert all(cell.priority_class in {"1B", "2B"} for cell in west)
    assert all(cell.priority_class in {"3A", "4A"} for cell in east)


def test_priority_geojson_is_wgs84_and_png_is_valid() -> None:
    """The export transforms projected cells and writes a PNG."""
    shade = _shade_fixture((40, 40))
    canopy = np.full((40, 40), 10.0, dtype=np.float64)
    cells = build_priority_grid(
        shade,
        bounds=(0.0, 0.0, 400.0, 400.0),
        crs=CRS,
        canopy_height=canopy,
        cell_size_m=200.0,
    )
    collection = priority_geojson(cells, crs=CRS, metadata={"method": "test"})
    features = cast("list[dict[str, object]]", collection["features"])
    feature = features[0]
    geometry = cast("dict[str, object]", feature["geometry"])
    coordinates = cast("list[list[list[float]]]", geometry["coordinates"])[0][0]
    assert -180.0 <= coordinates[0] <= 180.0
    assert -90.0 <= coordinates[1] <= 90.0
    assert priority_png(cells).startswith(b"\x89PNG")


def test_write_priority_product_writes_all_files(tmp_path: Path) -> None:
    """The product writer writes JSON, GeoJSON, and PNG."""
    shade = _shade_fixture((40, 40))
    canopy = np.full((40, 40), 10.0, dtype=np.float64)
    cells = build_priority_grid(
        shade,
        bounds=(0.0, 0.0, 400.0, 400.0),
        crs=CRS,
        canopy_height=canopy,
        cell_size_m=200.0,
    )
    paths = write_priority_product(
        cells,
        tmp_path,
        crs=CRS,
        metadata={"method": "test", "evidence": PRIORITY_EVIDENCE.to_dict()},
    )
    assert paths["json"].exists()
    assert paths["geojson"].exists()
    assert paths["png"].exists()
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == "fresh-urban-forest.heat-priority.v1"
    assert len(payload["cells"]) == len(cells)


def test_build_priority_grid_without_equity_is_unclassified() -> None:
    """Cells without an equity frame are retained but marked NA."""
    shade = _shade_fixture((40, 40))
    canopy = np.full((40, 40), 10.0, dtype=np.float64)
    cells = build_priority_grid(
        shade,
        bounds=(0.0, 0.0, 400.0, 400.0),
        crs=CRS,
        canopy_height=canopy,
        cell_size_m=200.0,
    )
    assert all(cell.priority_class == "NA" for cell in cells)
    assert all(cell.equity_score != cell.equity_score for cell in cells)


def test_build_priority_grid_rejects_bad_shape_and_cell_size() -> None:
    """Mismatched canopy or a non-positive cell size is rejected."""
    shade = _shade_fixture((40, 40))
    with pytest.raises(ValueError, match="match the shade"):
        build_priority_grid(
            shade,
            bounds=(0.0, 0.0, 400.0, 400.0),
            crs=CRS,
            canopy_height=np.zeros((39, 40)),
        )
    with pytest.raises(ValueError, match="cell_size_m"):
        build_priority_grid(
            shade,
            bounds=(0.0, 0.0, 400.0, 400.0),
            crs=CRS,
            canopy_height=np.zeros((40, 40)),
            cell_size_m=0.0,
        )
