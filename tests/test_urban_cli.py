"""Integration tests for the Fresh Urban Forest command line."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from fresh_urban_forest.cli import app
from tests.fixtures import make_dataset

RUNNER = CliRunner()


def test_catalog_commands() -> None:
    """The catalog can be listed, searched, and shown."""
    listed = RUNNER.invoke(app, ["catalog", "list"])
    assert listed.exit_code == 0
    assert "ubc_campus" in listed.stdout
    searched = RUNNER.invoke(app, ["catalog", "search", "lidar"])
    assert searched.exit_code == 0
    assert "ubc_lidar" in searched.stdout
    shown = RUNNER.invoke(app, ["catalog", "show", "ubc_campus_trees"])
    assert shown.exit_code == 0
    assert "tree_inventory" in shown.stdout


def test_info_detect_and_change(tmp_path: Path) -> None:
    """Dataset inspection, crown detection, and change comparison run end to end."""
    make_dataset(tmp_path / "first")
    info = RUNNER.invoke(app, ["info", "--dataset", str(tmp_path / "first" / "dataset")])
    assert info.exit_code == 0
    assert "Test urban forest" in info.stdout
    detected = RUNNER.invoke(
        app,
        [
            "detect-trees",
            "--dataset",
            str(tmp_path / "first" / "dataset"),
            "--out",
            str(tmp_path / "detected.geojson"),
            "--min-height",
            "2",
        ],
    )
    assert detected.exit_code == 0
    assert (tmp_path / "detected.geojson").exists()
    make_dataset(tmp_path / "second")
    change = RUNNER.invoke(
        app,
        [
            "change",
            "--earlier",
            str(tmp_path / "first" / "dataset"),
            "--later",
            str(tmp_path / "second" / "dataset"),
            "--out",
            str(tmp_path / "change.json"),
        ],
    )
    assert change.exit_code == 0
    assert (tmp_path / "change.json").exists()


def test_build_change_product(tmp_path: Path) -> None:
    """The CLI writes an observed-change product from two datasets."""
    make_dataset(tmp_path / "first")
    make_dataset(tmp_path / "second")
    result = RUNNER.invoke(
        app,
        [
            "build-change",
            "--earlier",
            str(tmp_path / "first" / "dataset"),
            "--later",
            str(tmp_path / "second" / "dataset"),
            "--out-dir",
            str(tmp_path / "change"),
        ],
    )
    assert result.exit_code == 0
    assert (tmp_path / "change" / "change.json").exists()
    assert (tmp_path / "change" / "change.png").exists()


def test_bad_bbox_is_rejected(tmp_path: Path) -> None:
    """A malformed bounding box exits with a usage error."""
    result = RUNNER.invoke(
        app,
        [
            "build",
            "--ubc-trees",
            str(tmp_path / "missing.geojson"),
            "--dem",
            str(tmp_path / "missing.tif"),
            "--out",
            str(tmp_path / "out"),
            "--bbox",
            "1,2",
        ],
    )
    assert result.exit_code != 0


def test_light_species_water_and_irrigation_commands(tmp_path: Path) -> None:
    """The light and species commands write their documented products."""
    make_dataset(tmp_path / "light")
    dataset = str(tmp_path / "light" / "dataset")
    shade = RUNNER.invoke(
        app,
        [
            "shade",
            "--dataset",
            dataset,
            "--date",
            "2026-06-21",
            "--mode",
            "day",
            "--times",
            "09:00,12:00,15:00",
            "--out-dir",
            str(tmp_path / "shade"),
        ],
    )
    assert shade.exit_code == 0, shade.stdout
    assert (tmp_path / "shade" / "shade.json").exists()
    assert (tmp_path / "shade" / "shade.png").exists()
    fit = RUNNER.invoke(
        app,
        [
            "species-fit",
            "--dataset",
            dataset,
            "--species",
            "Acer rubrum",
            "--out",
            str(tmp_path / "fit.json"),
        ],
    )
    assert fit.exit_code == 0, fit.stdout
    assert (tmp_path / "fit.json").exists()
    water = RUNNER.invoke(
        app,
        [
            "water",
            "--dataset",
            dataset,
            "--species",
            "Acer rubrum",
            "--out",
            str(tmp_path / "water.json"),
        ],
    )
    assert water.exit_code == 0, water.stdout
    assert (tmp_path / "water.json").exists()
    irrigation = RUNNER.invoke(
        app,
        [
            "irrigation",
            "--dataset",
            dataset,
            "--species",
            "Acer rubrum",
            "--out",
            str(tmp_path / "irrigation.json"),
        ],
    )
    assert irrigation.exit_code == 0, irrigation.stdout
    assert (tmp_path / "irrigation.json").exists()


def test_bad_shade_date_is_rejected(tmp_path: Path) -> None:
    """An invalid shade date is a usage error."""
    make_dataset(tmp_path / "bad-date")
    result = RUNNER.invoke(
        app,
        ["shade", "--dataset", str(tmp_path / "bad-date" / "dataset"), "--date", "nope"],
    )
    assert result.exit_code != 0


def test_optimize_and_pareto_commands(tmp_path: Path) -> None:
    """The optimizer and archive summary run end to end."""
    make_dataset(tmp_path / "optimize")
    result = RUNNER.invoke(
        app,
        [
            "optimize",
            "--dataset",
            str(tmp_path / "optimize" / "dataset"),
            "--out",
            str(tmp_path / "optimize.json"),
            "--sites",
            "6",
            "--horizon",
            "5",
            "--population",
            "6",
            "--generations",
            "1",
            "--scalarizations",
            "4",
            "--local-iterations",
            "10",
            "--workers",
            "1",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "optimize.json").exists()
    summary = RUNNER.invoke(
        app,
        [
            "pareto",
            "--archive",
            str(tmp_path / "optimize.json"),
            "--out",
            str(tmp_path / "pareto.json"),
        ],
    )
    assert summary.exit_code == 0, summary.stdout
    assert (tmp_path / "pareto.json").exists()


def test_off_inventory_command(tmp_path: Path) -> None:
    """The off-inventory command writes a candidate layer and VOI result."""
    make_dataset(tmp_path / "off")
    result = RUNNER.invoke(
        app,
        [
            "off-inventory",
            "--dataset",
            str(tmp_path / "off" / "dataset"),
            "--out-dir",
            str(tmp_path / "off-inventory"),
            "--min-height",
            "2",
            "--window",
            "2",
            "--min-confidence",
            "0.1",
            "--max-candidates",
            "20",
            "--voi",
            "--voi-sites",
            "6",
            "--voi-scalarizations",
            "4",
            "--voi-workers",
            "1",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "off-inventory" / "off_inventory.json").exists()
    assert (tmp_path / "off-inventory" / "off_inventory.geojson").exists()
    assert (tmp_path / "off-inventory" / "off_inventory_voi.json").exists()


def test_birds_command(tmp_path: Path) -> None:
    """The birds command writes a habitat and demography report."""
    make_dataset(tmp_path / "birds")
    result = RUNNER.invoke(
        app,
        [
            "birds",
            "--dataset",
            str(tmp_path / "birds" / "dataset"),
            "--out",
            str(tmp_path / "birds.json"),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "birds.json").exists()


def test_report_command(tmp_path: Path) -> None:
    """The report command writes a unified baseline report."""
    make_dataset(tmp_path / "report")
    result = RUNNER.invoke(
        app,
        [
            "report",
            "--dataset",
            str(tmp_path / "report" / "dataset"),
            "--out",
            str(tmp_path / "lab-report.json"),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "lab-report.json").exists()


def test_detect_trees_postprocess_writes_summary(tmp_path: Path) -> None:
    """The opt-in post-processing writes kept crowns and a sidecar summary."""
    make_dataset(tmp_path / "first")
    out = tmp_path / "detected_post.geojson"
    detected = RUNNER.invoke(
        app,
        [
            "detect-trees",
            "--dataset",
            str(tmp_path / "first" / "dataset"),
            "--out",
            str(out),
            "--min-height",
            "2",
            "--postprocess",
            "--buffer",
            "5",
            "--max-small-height",
            "2",
        ],
    )
    assert detected.exit_code == 0
    assert out.exists()
    summary = out.with_suffix(".summary.json")
    assert summary.exists()
    payload = json.loads(summary.read_text())
    assert payload["tree_count"] >= 0
    assert "buffer_ids" in payload
    assert "small_ids" in payload
    assert "merge_groups" in payload
    assert "kept_ids" in payload
