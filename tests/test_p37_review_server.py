"""Tests for the P37 review-server persistence helpers."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

import p37_review_server


def test_review_server_helpers_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Server helpers validate IDs and persist the latest label snapshot."""
    root = tmp_path / "packet"
    root.mkdir()
    with (root / "review_template.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["candidate_id", "human_label", "notes"])
        writer.writeheader()
        writer.writerow({"candidate_id": "c1", "human_label": "", "notes": ""})
    submissions = root / "submissions"
    monkeypatch.setattr(p37_review_server, "ROOT", root)
    monkeypatch.setattr(p37_review_server, "SUBMISSIONS", submissions)
    monkeypatch.setattr(p37_review_server, "LATEST", submissions / "labels_latest.json")
    monkeypatch.setattr(p37_review_server, "EVENTS", submissions / "labels.jsonl")
    assert p37_review_server._valid_ids() == {"c1"}
    p37_review_server._write_latest({"c1": {"label": "C"}})
    assert p37_review_server._latest()["labels"] == {"c1": {"label": "C"}}
