"""Tests for City of Vancouver LiDAR tile discovery."""

from __future__ import annotations

import httpx
import pytest

from fresh_urban_forest.vancouver import discover_vancouver_tiles

BBOX = (-123.30, 49.20, -123.10, 49.32)


def _payload() -> dict[str, object]:
    """Build a two-record tile index response."""

    def record(name: str, url: str, coordinates: list[list[list[float]]]) -> dict[str, object]:
        return {
            "name": name,
            "lidar_url": url,
            "geom": {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": coordinates},
            },
        }

    return {
        "total_count": 2,
        "results": [
            record(
                "4810E_54560N",
                "https://example.test/4810E_54560N.zip",
                [[[-123.30, 49.20], [-123.10, 49.20], [-123.10, 49.32], [-123.30, 49.20]]],
            ),
            record(
                "9000E_90000N",
                "https://example.test/9000E_90000N.zip",
                [[[-100.0, 40.0], [-99.0, 40.0], [-99.0, 41.0], [-100.0, 40.0]]],
            ),
        ],
    }


def test_discover_vancouver_tiles_filters_by_bbox() -> None:
    """Only intersecting tiles are returned and the key fields are normalised."""
    requested: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request)
        return httpx.Response(200, json=_payload())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        tiles = discover_vancouver_tiles(2022, BBOX, client=client, page_size=10)
    assert len(tiles) == 1
    tile = tiles[0]
    assert tile.source == "vancouver-lidar-2022"
    assert tile.tile_id == "4810E_54560N"
    assert tile.density == 49.0
    assert tile.year == 2022
    assert tile.bbox == (-123.30, 49.20, -123.10, 49.32)
    assert "vancouver" in requested[0].url.host


def test_discover_vancouver_rejects_unknown_year() -> None:
    """An unsupported year is refused."""
    with pytest.raises(ValueError, match="unsupported"):
        discover_vancouver_tiles(2024, BBOX)
