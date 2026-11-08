"""Tests for deterministic spatial control-tile selection."""

from __future__ import annotations

import pytest

from select_vancouver_control_tiles import CITY_BOUNDS_WGS84, select_tiles


def _tile(tile_id: str, lon: float, lat: float, size: int) -> dict[str, object]:
    """Build a synthetic index tile."""
    return {
        "tile_id": tile_id,
        "filename": f"{tile_id}.zip",
        "bbox": [lon - 0.005, lat - 0.005, lon + 0.005, lat + 0.005],
        "size_bytes": size,
        "url": f"https://example.test/{tile_id}.zip",
        "sha256": tile_id,
    }


def test_select_tiles_chooses_smallest_per_bin_and_is_bounded() -> None:
    """One deterministic tile is selected per populated bin."""
    left, bottom, right, top = CITY_BOUNDS_WGS84
    lon = (left + right) / 2
    lat = (bottom + top) / 2
    tiles = [
        _tile("large", lon, lat, 900),
        _tile("small", lon + 0.0001, lat, 100),
        _tile("other", left + 0.01, top - 0.01, 300),
    ]
    selected = select_tiles(tiles, bounds=CITY_BOUNDS_WGS84, bins=6, min_tiles=1, max_tiles=10)
    ids = [str(tile["tile_id"]) for tile in selected]
    assert "small" in ids
    assert "large" not in ids
    assert len(ids) == len(set(ids))


def test_select_tiles_rejects_out_of_bounds_target() -> None:
    """An impossible sample size is an explicit error."""
    with pytest.raises(ValueError, match="expected"):
        select_tiles([], bounds=CITY_BOUNDS_WGS84, bins=6, min_tiles=1, max_tiles=10)
    with pytest.raises(ValueError, match="limits"):
        select_tiles([], bounds=CITY_BOUNDS_WGS84, bins=6, min_tiles=10, max_tiles=1)
