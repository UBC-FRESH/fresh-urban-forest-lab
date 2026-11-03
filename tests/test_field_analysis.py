"""Tests for completed field-packet analysis."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from fresh_urban_forest.field_analysis import analyze_field_packet, write_field_analysis


def _write_packet(packet: Path) -> None:
    """Write a small completed packet."""
    packet.mkdir(parents=True, exist_ok=True)
    with (packet / "field_checks.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "tree_id",
                "lon",
                "lat",
                "species",
                "dbh_cm",
                "height_m",
                "crown_width_m",
                "detected_height_m",
                "detected_crown_radius_m",
                "field_verified",
                "field_dbh_cm",
                "field_height_m",
                "field_crown_width_m",
                "field_notes",
            ]
        )
        writer.writerow(
            ["t1", -123.25, 49.26, "Acer", 20, 12, 6, 12.5, 3.2, "yes", 21, 12.0, 6.0, ""]
        )
        writer.writerow(
            ["t2", -123.25, 49.26, "Acer", 20, 12, 6, "", "", "missing", "", "", "", ""]
        )
        writer.writerow(["t3", -123.25, 49.26, "Acer", 20, 12, 6, "", "", "new", "", 8.0, 4.0, ""])
        writer.writerow(["t4", -123.25, 49.26, "Acer", 20, 12, 6, "", "", "", "", "", "", ""])
    with (packet / "detected_checks.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "detected_id",
                "lon",
                "lat",
                "detected_height_m",
                "detected_crown_radius_m",
                "field_status",
                "field_notes",
            ]
        )
        writer.writerow(["d1", -123.25, 49.26, 12.5, 3.2, "real", ""])
        writer.writerow(["d2", -123.25, 49.26, 12.5, 3.2, "merged", ""])
        writer.writerow(["d3", -123.25, 49.26, 12.5, 3.2, "false_positive", ""])
        writer.writerow(["d4", -123.25, 49.26, 12.5, 3.2, "", ""])


def test_analyze_field_packet(tmp_path: Path) -> None:
    """Verified rows drive precision, recall, and bias."""
    packet = tmp_path / "packet"
    _write_packet(packet)
    result = analyze_field_packet(packet)
    assert result.inventory_rows == 4
    assert result.verified_present == 1
    assert result.missing_trees == 1
    assert result.new_trees == 1
    assert result.unverified_trees == 1
    assert result.detected_rows == 4
    assert result.detected_real == 1
    assert result.detected_merged == 1
    assert result.detected_false_positive == 1
    assert result.detected_unverified == 1
    assert result.precision == 0.3333
    assert result.precision_including_merged == 0.6667
    assert result.recall == 0.6667
    assert result.mean_height_bias_m == 0.5
    assert result.mean_crown_radius_bias_m == 0.2


def test_write_field_analysis(tmp_path: Path) -> None:
    """The analysis writes JSON and Markdown."""
    packet = tmp_path / "packet"
    _write_packet(packet)
    result = analyze_field_packet(packet)
    path = write_field_analysis(result, tmp_path / "out")
    payload = json.loads(path.read_text())
    assert payload["precision"] == 0.3333
    assert (tmp_path / "out" / "field_analysis.md").exists()
