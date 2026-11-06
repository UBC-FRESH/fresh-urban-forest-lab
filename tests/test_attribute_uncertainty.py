"""Tests for candidate attribute envelopes."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import cast

from attach_attribute_uncertainty import attribute_envelope, main


def test_attribute_envelope_has_method_fields() -> None:
    """Ranges surround the point estimates and carry an evidence tier."""
    fields = attribute_envelope(
        {
            "height_m": 10.0,
            "crown_radius_m": 3.0,
            "dbh_cm": 20.0,
            "crown_volume_m3": 100.0,
            "carbon_kg": 50.0,
        }
    )
    # Values are stored as JSON-safe floats in production; cast for the type checker.
    assert cast(float, fields["height_low_m"]) < 10.0 < cast(float, fields["height_high_m"])
    assert (
        cast(float, fields["crown_radius_low_m"]) < 3.0 < cast(float, fields["crown_radius_high_m"])
    )
    assert cast(float, fields["dbh_low_cm"]) < 20.0 < cast(float, fields["dbh_high_cm"])
    assert cast(float, fields["carbon_low_kg"]) < 50.0 < cast(float, fields["carbon_high_kg"])
    assert "allometric" in str(fields["attribute_evidence"])


def test_attribute_main_updates_layer_and_summary(tmp_path: Path) -> None:
    """The command writes envelope fields and aggregate totals."""
    candidates = tmp_path / "candidates.geojson.gz"
    with gzip.open(candidates, "wt", encoding="utf-8") as handle:
        json.dump(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [-123.0, 49.0]},
                        "properties": {
                            "candidate_id": "c1",
                            "height_m": 10.0,
                            "crown_radius_m": 3.0,
                            "dbh_cm": 20.0,
                            "crown_volume_m3": 100.0,
                            "carbon_kg": 50.0,
                        },
                    }
                ],
            },
            handle,
        )
    summary = tmp_path / "summary.json"
    summary.write_text(json.dumps({"candidate_count": 1}), encoding="utf-8")
    output = tmp_path / "out.geojson.gz"
    assert (
        main(
            [
                "--candidates",
                str(candidates),
                "--summary",
                str(summary),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    with gzip.open(output, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    properties = payload["features"][0]["properties"]
    assert properties["height_high_m"] == 12.0
    updated = json.loads(summary.read_text())
    assert updated["attribute_totals"]["carbon_low_kg"] == 25.0
    assert updated["attribute_schema"]["carbon"]["unit"] == "kg"
