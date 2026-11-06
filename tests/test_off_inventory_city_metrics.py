"""Tests for city-tab candidate metrics."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from build_off_inventory_city_metrics import aggregate, main


def _feature(candidate_id: str, confidence: float, land: str, carbon: float) -> dict[str, object]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-123.0, 49.0]},
        "properties": {
            "candidate_id": candidate_id,
            "confidence": confidence,
            "land_class": land,
            "crown_area_m2": 10.0,
            "crown_volume_m3": 20.0,
            "crown_volume_low_m3": 10.0,
            "crown_volume_high_m3": 30.0,
            "carbon_kg": carbon,
            "carbon_low_kg": carbon / 2,
            "carbon_high_kg": carbon * 1.5,
        },
    }


def test_aggregate_separates_likely_private_and_confidence() -> None:
    """The likely-private totals count high-confidence candidates separately."""
    payload = aggregate(
        [
            _feature("c1", 0.8, "likely private parcel", 100.0),
            _feature("c2", 0.4, "likely private parcel", 50.0),
            _feature("c3", 0.9, "street/lane", 25.0),
        ]
    )
    likely = payload["likely_private"]
    assert isinstance(likely, dict)
    assert likely["candidate_count"] == 2
    assert likely["high_confidence_count"] == 1
    assert likely["carbon_kg"] == 150.0
    all_metrics = payload["all"]
    assert isinstance(all_metrics, dict)
    assert all_metrics["candidate_count"] == 3


def test_main_writes_metrics(tmp_path: Path) -> None:
    """The command reads the candidate GeoJSON and writes metrics JSON."""
    candidates = tmp_path / "candidates.geojson.gz"
    with gzip.open(candidates, "wt", encoding="utf-8") as handle:
        json.dump(
            {
                "type": "FeatureCollection",
                "features": [_feature("c1", 0.8, "likely private parcel", 100.0)],
            },
            handle,
        )
    output = tmp_path / "metrics.json"
    assert main(["--candidates", str(candidates), "--output", str(output)]) == 0
    payload = json.loads(output.read_text())
    assert payload["likely_private"]["candidate_count"] == 1
