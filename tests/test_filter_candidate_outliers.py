"""Tests for filtering implausibly large watershed crowns."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from filter_candidate_outliers import main


def _feature(candidate_id: str, radius: float) -> dict[str, object]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-123.0, 49.0]},
        "properties": {
            "candidate_id": candidate_id,
            "confidence": 0.8,
            "crown_radius_m": radius,
            "crown_area_m2": radius * radius * 3.14,
            "crown_volume_m3": 100.0,
            "carbon_kg": 50.0,
            "height_low_m": 8.0,
            "height_high_m": 12.0,
            "crown_volume_low_m3": 50.0,
            "crown_volume_high_m3": 150.0,
            "carbon_low_kg": 25.0,
            "carbon_high_kg": 75.0,
            "land_class": "likely private parcel",
            "support_class": "high",
        },
    }


def test_filter_removes_oversized_crowns(tmp_path: Path) -> None:
    """A 500 m-radius flood segment is removed and totals are recomputed."""
    candidates = tmp_path / "candidates.geojson.gz"
    with gzip.open(candidates, "wt", encoding="utf-8") as handle:
        json.dump(
            {
                "type": "FeatureCollection",
                "features": [_feature("ok", 3.0), _feature("huge", 500.0)],
            },
            handle,
        )
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps(
            {
                "candidate_count": 2,
                "attribute_totals": {
                    "height_low_m": 0,
                    "height_high_m": 0,
                    "crown_volume_low_m3": 0,
                    "crown_volume_high_m3": 0,
                    "carbon_low_kg": 0,
                    "carbon_high_kg": 0,
                },
                "point_support": {"classes": {}},
                "land_classes": {},
            }
        ),
        encoding="utf-8",
    )
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
    assert len(payload["features"]) == 1
    updated = json.loads(summary.read_text())
    assert updated["candidate_count"] == 1
    assert updated["outlier_filter"]["removed"] == 1
