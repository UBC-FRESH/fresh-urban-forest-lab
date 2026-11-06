"""Tests for the blind human verification packet."""

from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image

from build_human_verification_packet import main


def test_packet_build_copies_images_and_hides_prior_labels(tmp_path: Path) -> None:
    """The HTML contains crops and IDs but not the prior AI label field."""
    crops = tmp_path / "crops"
    crops.mkdir()
    labels = tmp_path / "labels.csv"
    rows = []
    for index, candidate_id in enumerate(("c1", "c2")):
        Image.new("RGB", (32, 32), (60 + index, 120, 70)).save(crops / f"{candidate_id}.png")
        rows.append(
            {
                "candidate_id": candidate_id,
                "confidence": "0.8",
                "height_m": "10",
                "crown_radius_m": "3",
                "land_class": "likely private parcel",
                "local_area": "A",
                "audit_label": "T" if index == 0 else "N",
            }
        )
    with labels.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    out = tmp_path / "packet"
    assert (
        main(
            [
                "--labels",
                str(labels),
                "--crops",
                str(crops),
                "--out-dir",
                str(out),
                "--no-zip",
            ]
        )
        == 0
    )
    html = (out / "index.html").read_text(encoding="utf-8")
    assert '"c1"' in html
    assert '"c2"' in html
    assert "audit_label" not in html
    assert (out / "images" / "c1.png").exists()
    assert (out / "review_template.csv").exists()
    metadata = (out / "candidate_metadata.csv").read_text(encoding="utf-8")
    assert "ai_label" in metadata
