"""Tests for the city off-inventory build script helpers."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from build_vancouver_off_inventory import (
    load_detected,
    load_trees,
    parse_args,
    save_detected,
)
from fresh_urban_forest.itd import DetectedTree


def test_parse_args_selects_detection_cache() -> None:
    """The cache reuse flag is parsed."""
    args = parse_args(["--reuse-detected"])
    assert args.reuse_detected is True
    assert args.detected_cache.name == "detected_city.json.gz"


def test_tree_and_detection_round_trip(tmp_path: Path) -> None:
    """Compressed tree and detection files round-trip through the helpers."""
    tree_path = tmp_path / "trees.json.gz"
    with gzip.open(tree_path, "wt", encoding="utf-8") as handle:
        json.dump(
            [
                {
                    "tree_id": "public-1",
                    "lon": -123.0,
                    "lat": 49.0,
                    "height_m": 9.0,
                    "x_m": 1.0,
                    "y_m": 2.0,
                }
            ],
            handle,
        )
    trees = load_trees(tree_path)
    assert trees[0].tree_id == "public-1"
    assert trees[0].height_m == 9.0

    detected_path = tmp_path / "detected.json.gz"
    crown = DetectedTree("city-1", 0, 0, 9.0, 3.0, 28.3, 1.0, 2.0, -123.0, 49.0)
    save_detected((crown,), detected_path)
    loaded = load_detected(detected_path)
    assert loaded == (crown,)
