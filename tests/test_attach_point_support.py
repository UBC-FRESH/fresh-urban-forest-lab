"""Tests for attaching point support to candidate properties."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from attach_point_support import main, support_class


def test_support_class_thresholds() -> None:
    """Support classes follow the documented thresholds."""
    assert support_class(0) == "none"
    assert support_class(1) == "low"
    assert support_class(499) == "low"
    assert support_class(500) == "medium"
    assert support_class(999) == "medium"
    assert support_class(1000) == "high"


def test_attach_support_updates_layer_and_summary(tmp_path: Path) -> None:
    """Support fields and summary counts are written atomically."""
    candidates = tmp_path / "candidates.geojson.gz"
    with gzip.open(candidates, "wt", encoding="utf-8") as handle:
        json.dump(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [-123.0, 49.0]},
                        "properties": {"candidate_id": "c1"},
                    },
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [-123.0, 49.0]},
                        "properties": {"candidate_id": "c2"},
                    },
                ],
            },
            handle,
        )
    support = tmp_path / "support.json.gz"
    with gzip.open(support, "wt", encoding="utf-8") as handle:
        json.dump([{"candidate_id": "c1", "point_count": 1200, "point_density": 4.2}], handle)
    summary = tmp_path / "summary.json"
    summary.write_text(json.dumps({"candidate_count": 2}), encoding="utf-8")
    output = tmp_path / "out.geojson.gz"
    assert (
        main(
            [
                "--candidates",
                str(candidates),
                "--support",
                str(support),
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
    assert properties["support_class"] == "high"
    assert properties["point_count"] == 1200
    assert payload["features"][1]["properties"]["support_class"] == "none"
    updated = json.loads(summary.read_text())
    assert updated["point_support"]["classes"] == {
        "none": 1,
        "low": 0,
        "medium": 0,
        "high": 1,
    }
