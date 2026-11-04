"""Tests for off-inventory detection and value-of-information screening."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from fresh_urban_forest.dataset import build_dataset
from fresh_urban_forest.models import UrbanForestDataset
from fresh_urban_forest.off_inventory import (
    augment_dataset,
    detect_off_inventory,
    value_of_information,
    write_report,
    write_value_of_information,
)
from tests.fixtures import make_raster


def _empty_dataset(tmp_path: Path) -> UrbanForestDataset:
    """Build a synthetic dataset with canopy but no official trees."""
    rows = cols = 30
    dem = make_raster(tmp_path / "dem.tif", np.zeros((rows, cols), dtype=np.float32))
    chm = make_raster(tmp_path / "chm.tif", np.zeros((rows, cols), dtype=np.float32))
    chm.array[4:12, 4:12] = 12.0
    chm.array[18:25, 18:25] = 9.0
    return build_dataset(
        name="Off-inventory test",
        trees=(),
        dem=dem,
        chm=chm,
        out_dir=tmp_path / "dataset",
        generated_utc="2026-11-04T00:00:00Z",
    )


def test_detection_creates_candidates_and_augmented_population(tmp_path: Path) -> None:
    """Unmatched detected crowns become filtered candidates and extra trees."""
    dataset = _empty_dataset(tmp_path)
    report = detect_off_inventory(
        dataset,
        dataset.terrain,
        min_height_m=3.0,
        window_m=4.0,
        min_confidence=0.1,
        max_candidates=20,
    )
    assert report.detected_count >= 1
    assert report.matched_count == 0
    assert report.candidate_count >= 1
    assert report.candidate_area_m2 > 0
    assert all(0.0 <= candidate.confidence <= 1.0 for candidate in report.candidates)
    assert "ownership unknown" in report.candidates[0].land_class
    augmented = augment_dataset(dataset, report)
    assert len(augmented.trees) == len(dataset.trees) + report.candidate_count
    assert "candidate_id" in augmented.trees[-1].attributes


def test_report_writer_and_geojson(tmp_path: Path) -> None:
    """The report writes JSON, GeoJSON, and a value-of-information file."""
    dataset = _empty_dataset(tmp_path)
    report = detect_off_inventory(
        dataset,
        dataset.terrain,
        min_height_m=3.0,
        window_m=4.0,
        min_confidence=0.1,
    )
    path = write_report(report, tmp_path / "off")
    assert path.exists()
    assert (tmp_path / "off" / "off_inventory.geojson").exists()
    value = value_of_information(
        dataset,
        report,
        sites=6,
        horizon=5,
        scalarizations=4,
        population=6,
        generations=1,
        local_iterations=10,
        workers=1,
    )
    voi_path = write_value_of_information(value, tmp_path / "off" / "voi.json")
    assert voi_path.exists()
    assert 0.0 <= value.plan_jaccard <= 1.0
    assert value.candidate_count == report.candidate_count


def test_empty_candidate_report_is_stable(tmp_path: Path) -> None:
    """A report with no candidates still has a valid schema and GeoJSON."""
    dataset = _empty_dataset(tmp_path)
    report = detect_off_inventory(
        dataset,
        dataset.terrain,
        min_height_m=100.0,
    )
    assert report.candidate_count == 0
    payload = report.to_geojson()
    assert payload["type"] == "FeatureCollection"
    assert payload["features"] == []
