"""Tests for the unified lab report."""

from __future__ import annotations

from pathlib import Path

from fresh_urban_forest.integration import build_lab_report, write_lab_report
from tests.fixtures import make_dataset


def test_baseline_report_contains_every_layer(tmp_path: Path) -> None:
    """The baseline report composes metrics, shade, birds, and completeness."""
    dataset = make_dataset(tmp_path)
    report = build_lab_report(dataset, include_shade=False, include_birds=False)
    scenario = report["scenario"]
    metrics = report["metrics"]
    completeness = report["completeness"]
    assert isinstance(scenario, dict)
    assert isinstance(metrics, dict)
    assert isinstance(completeness, dict)
    assert report["schema_version"] == "fresh-urban-forest.lab-report.v1"
    assert scenario["is_scenario"] is False
    assert metrics["tree_count"] > 0
    assert "fields" in completeness
    assert report["off_inventory"] is None
    assert report["caveats"]
    path = write_lab_report(report, tmp_path / "report.json")
    assert path.exists()


def test_report_with_shade_birds_and_off_inventory(tmp_path: Path) -> None:
    """Optional layers add evidence-bearing sections."""
    dataset = make_dataset(tmp_path)
    off_inventory = {
        "candidate_count": 3,
        "candidate_area_m2": 12.5,
        "detected_count": 10,
        "matched_count": 7,
    }
    report = build_lab_report(
        dataset,
        off_inventory=off_inventory,
        scenario_id="scenario-test",
        scenario_name="Test scenario",
        year=3,
    )
    scenario = report["scenario"]
    birds = report["birds"]
    off_inventory_report = report["off_inventory"]
    assert isinstance(scenario, dict)
    assert isinstance(birds, dict)
    assert isinstance(off_inventory_report, dict)
    assert scenario["scenario_id"] == "scenario-test"
    assert scenario["year"] == 3
    assert "shade" in report
    assert off_inventory_report["candidate_count"] == 3
    assert len(birds["guilds"]) == 5
    assert report["evidence"]
