"""Tests for the canopy-gap and planting-opportunity screen."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import numpy as np
import pytest

from fresh_urban_forest.planting_opportunity import (
    GAP_EVIDENCE,
    OPPORTUNITY_EVIDENCE,
    build_gap_masks,
    build_opportunity_grid,
    opportunity_geojson,
    opportunity_png,
    slope_degrees,
    write_opportunity_product,
)

CRS = "EPSG:3157"
BOUNDS = (493_000.0, 5_455_000.0, 493_600.0, 5_455_600.0)


def _masks() -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
]:
    """Build a 60 by 60 synthetic mask set."""
    shape = (60, 60)
    dem = np.zeros(shape, dtype=np.float64)
    canopy = np.zeros(shape, dtype=np.float64)
    canopy[10:20, 10:20] = 15.0
    building = np.zeros(shape, dtype=np.bool_)
    building[30:35, 45:50] = True
    water = np.zeros(shape, dtype=np.bool_)
    water[50:56, 5:10] = True
    surface = np.zeros(shape, dtype=np.bool_)
    surface[:, 25] = True
    centre = np.zeros(shape, dtype=np.bool_)
    centre[:, 25] = True
    return dem, canopy, building, water, surface, centre


def _priority() -> dict[str, dict[str, object]]:
    """Return priority rows for a 3 by 3 200 m grid."""
    return {
        f"r{row:02d}c{col:02d}": {
            "shade_deficit": 0.8 if col == 0 else 0.3,
            "equity_score": 0.9 if row == 0 else 0.2,
            "priority_class": "1A" if row == 0 and col == 0 else "4B",
        }
        for row in range(3)
        for col in range(3)
    }


def test_slope_degrees_flat_and_ramp() -> None:
    """Flat ground has zero slope and a ramp has a positive slope."""
    flat = slope_degrees(np.zeros((10, 10)), 5.0)
    ramp = np.tile(np.arange(10, dtype=np.float64) * 5.0, (10, 1))
    sloped = slope_degrees(ramp, 5.0)
    assert float(np.max(flat)) == pytest.approx(0.0)
    assert float(np.max(sloped)) > 0.0
    with pytest.raises(ValueError, match="two-dimensional"):
        slope_degrees(np.zeros((2, 2, 2)), 5.0)
    with pytest.raises(ValueError, match="positive"):
        slope_degrees(np.zeros((2, 2)), 0.0)


def test_build_gap_masks_splits_gap_and_street_gap() -> None:
    """The gap is near canopy, the street gap is near the road, and interior is separate."""
    dem, canopy, building, water, surface, centre = _masks()
    masks = build_gap_masks(
        dem=dem,
        canopy_height=canopy,
        building_mask=building,
        water_mask=water,
        road_surface_mask=surface,
        road_center_mask=centre,
        cell_size_m=10.0,
        gap_distance_m=20.0,
        street_distance_m=50.0,
    )
    assert masks.gap.any()
    assert masks.street_gap.any()
    assert masks.interior_open.any()
    assert np.all(~masks.gap[canopy >= 2.0])
    assert np.all(masks.street_gap <= masks.gap)
    assert masks.summary["gap_m2"] > 0.0
    assert 0.0 <= masks.summary["street_gap_share"] <= 1.0
    assert masks.evidence == GAP_EVIDENCE
    assert masks.to_dict()["summary"] == masks.summary


def test_build_gap_masks_rejects_shape_and_distance() -> None:
    """Mismatched masks and negative distances are rejected."""
    dem = np.zeros((4, 4))
    with pytest.raises(ValueError, match="share the DEM shape"):
        build_gap_masks(
            dem=dem,
            canopy_height=np.zeros((5, 4)),
            building_mask=np.zeros((4, 4), dtype=bool),
            water_mask=np.zeros((4, 4), dtype=bool),
            road_surface_mask=np.zeros((4, 4), dtype=bool),
            road_center_mask=np.zeros((4, 4), dtype=bool),
            cell_size_m=5.0,
        )
    with pytest.raises(ValueError, match="non-negative"):
        build_gap_masks(
            dem=dem,
            canopy_height=np.zeros((4, 4)),
            building_mask=np.zeros((4, 4), dtype=bool),
            water_mask=np.zeros((4, 4), dtype=bool),
            road_surface_mask=np.zeros((4, 4), dtype=bool),
            road_center_mask=np.zeros((4, 4), dtype=bool),
            cell_size_m=5.0,
            gap_distance_m=-1.0,
        )


def test_build_opportunity_grid_aggregates_and_classifies() -> None:
    """Cells carry gap area, site counts, capacity, P38 fields, and a tier."""
    dem, canopy, building, water, surface, centre = _masks()
    masks = build_gap_masks(
        dem=dem,
        canopy_height=canopy,
        building_mask=building,
        water_mask=water,
        road_surface_mask=surface,
        road_center_mask=centre,
        cell_size_m=10.0,
        gap_distance_m=20.0,
        street_distance_m=50.0,
    )
    cells = build_opportunity_grid(
        masks,
        bounds=BOUNDS,
        crs=CRS,
        priority=_priority(),
        cell_size_m=200.0,
    )
    assert cells
    assert all(cell.gap_m2 >= 0.0 for cell in cells)
    assert any(cell.gap_sites > 0 for cell in cells)
    assert any(cell.street_gap_sites > 0 for cell in cells)
    assert all(cell.capacity_small_upper >= cell.capacity_medium_upper for cell in cells)
    assert all(cell.opportunity_tier in {"high", "medium", "low", "none"} for cell in cells)
    assert all(cell.priority_class in {"1A", "4B", "NA"} for cell in cells)


def test_geojson_and_png_exports() -> None:
    """The exports transform cells to WGS84 and produce a PNG."""
    dem, canopy, building, water, surface, centre = _masks()
    masks = build_gap_masks(
        dem=dem,
        canopy_height=canopy,
        building_mask=building,
        water_mask=water,
        road_surface_mask=surface,
        road_center_mask=centre,
        cell_size_m=10.0,
        gap_distance_m=20.0,
        street_distance_m=50.0,
    )
    cells = build_opportunity_grid(
        masks,
        bounds=BOUNDS,
        crs=CRS,
        priority=_priority(),
        cell_size_m=200.0,
    )
    collection = opportunity_geojson(cells, crs=CRS, metadata={"method": "test"})
    features = cast("list[dict[str, object]]", collection["features"])
    geometry = cast("dict[str, object]", features[0]["geometry"])
    coordinates = cast("list[list[list[float]]]", geometry["coordinates"])[0][0]
    assert -180.0 <= coordinates[0] <= 180.0
    assert -90.0 <= coordinates[1] <= 90.0
    assert opportunity_png(cells).startswith(b"\x89PNG")


def test_write_opportunity_product(tmp_path: Path) -> None:
    """The writer writes JSON, GeoJSON, and PNG with the expected schema."""
    dem, canopy, building, water, surface, centre = _masks()
    masks = build_gap_masks(
        dem=dem,
        canopy_height=canopy,
        building_mask=building,
        water_mask=water,
        road_surface_mask=surface,
        road_center_mask=centre,
        cell_size_m=10.0,
        gap_distance_m=20.0,
        street_distance_m=50.0,
    )
    cells = build_opportunity_grid(
        masks,
        bounds=BOUNDS,
        crs=CRS,
        priority=_priority(),
        cell_size_m=200.0,
    )
    paths = write_opportunity_product(
        cells,
        tmp_path,
        crs=CRS,
        metadata={"method": "test", "evidence": OPPORTUNITY_EVIDENCE.to_dict()},
    )
    assert paths["json"].exists()
    assert paths["geojson"].exists()
    assert paths["png"].exists()
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == "fresh-urban-forest.planting-opportunity.v1"
    assert len(payload["cells"]) == len(cells)
