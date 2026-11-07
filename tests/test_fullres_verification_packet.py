"""Tests for the P37 blind human-verification packet."""

from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import build_fullres_verification_packet as packet


class _FakeSource:
    """Minimal full-resolution source stand-in."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.closed = False

    def chip(self, _x: float, _y: float, *, size: int) -> np.ndarray:
        """Return a blank RGB crop."""
        return np.zeros((size, size, 3), dtype=np.uint8)

    def close(self) -> None:
        """Mark the source closed."""
        self.closed = True


def test_packet_builds_blind_species_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The packet includes species choices and hides prior probabilities."""
    monkeypatch.setattr(packet, "FullResolutionSource", _FakeSource)
    features = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-122.85, 49.18]},
                "properties": {"candidate_id": "surrey-off-test", "confidence": 0.8},
            }
        ],
    }
    features_path = tmp_path / "features.geojson.gz"
    with gzip.open(features_path, "wt", encoding="utf-8") as handle:
        json.dump(features, handle)
    audit_path = tmp_path / "audit.csv"
    with audit_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["candidate_index", "candidate_id", "page", "p_fullres", "p_030"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "candidate_index": "0",
                "candidate_id": "surrey-off-test",
                "page": "1",
                "p_fullres": "0.91",
                "p_030": "0.72",
            }
        )
    out = tmp_path / "packet"
    assert (
        packet.main(
            [
                "--audit-csv",
                str(audit_path),
                "--vrt",
                str(tmp_path / "unused.vrt"),
                "--features",
                str(features_path),
                "--out-dir",
                str(out),
                "--no-zip",
            ]
        )
        == 0
    )
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "surrey-off-test" in html
    assert "Conifer" in html
    assert "Deciduous" in html
    assert "p_fullres" not in html
    assert (out / "images" / "000000.png").is_file()
    assert Image.open(out / "images" / "000000.png").size == (384, 384)
    with (out / "review_template.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["candidate_id"] == "surrey-off-test"
    assert rows[0]["human_label"] == ""
    metadata = (out / "candidate_metadata.csv").read_text(encoding="utf-8")
    assert "p_fullres" in metadata
