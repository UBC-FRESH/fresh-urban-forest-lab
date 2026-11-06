"""Tests for the compact 3D candidate payload."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from build_off_inventory_3d import compact_payload, main


def _feature(confidence: float) -> dict[str, object]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-123.0, 49.0]},
        "properties": {
            "candidate_id": "c1",
            "confidence": confidence,
            "height_m": 10.0,
            "crown_radius_m": 3.0,
            "crown_area_m2": 28.3,
            "dbh_cm": 20.0,
            "crown_volume_m3": 100.0,
            "carbon_kg": 50.0,
            "point_count": 1200,
            "land_class": "likely private parcel",
        },
    }


def test_compact_payload_filters_confidence_and_adds_ids() -> None:
    """Only high-confidence candidates enter the 3D arrays."""
    payload = compact_payload([_feature(0.8), _feature(0.4)])
    assert payload["count"] == 1
    assert payload["candidate_id"] == ["c1"]
    assert payload["land_code"] == [0]
    assert payload["x_m"]


def test_main_writes_payload(tmp_path: Path) -> None:
    """The command writes the compact 3D file."""
    candidates = tmp_path / "candidates.geojson.gz"
    with gzip.open(candidates, "wt", encoding="utf-8") as handle:
        json.dump({"type": "FeatureCollection", "features": [_feature(0.8)]}, handle)
    output = tmp_path / "candidates3d.json.gz"
    assert main(["--candidates", str(candidates), "--output", str(output)]) == 0
    with gzip.open(output, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert payload["count"] == 1
    assert payload["candidate_id"] == ["c1"]
