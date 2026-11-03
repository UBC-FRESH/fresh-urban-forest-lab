"""Tests for LidarBC and CanElevation tile discovery."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import httpx
import pytest
from shapely.geometry import Point

from fresh_urban_forest.canelevation import discover_canelevation_tiles
from fresh_urban_forest.lidarbc import discover_lidarbc_tiles
from fresh_urban_forest.tiles import (
    LidarTile,
    download_tiles,
    make_manifest,
    read_tile_manifest,
    tiles_to_geojson,
    write_tile_manifest,
)

BBOX = (-123.30, 49.20, -123.10, 49.32)


def _lidarbc_payload() -> dict[str, object]:
    """Build a minimal LidarBC GeoJSON response."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-123.30, 49.20],
                            [-123.10, 49.20],
                            [-123.10, 49.32],
                            [-123.30, 49.32],
                            [-123.30, 49.20],
                        ]
                    ],
                },
                "properties": {
                    "OBJECTID": 1,
                    "maptile": "092g024_2_3_4",
                    "filename": "bc_092g024_2_3_4.laz",
                    "s3Url": "https://example.test/bc_092g024_2_3_4.laz",
                    "s3RptUrl": "https://example.test/report.pdf",
                    "year": 2016,
                    "projection": "utm10",
                    "density": 8,
                    "oper_name": "NDMP Fraser 2016",
                    "classes": "[1, 2]",
                },
            }
        ],
    }


def test_discover_lidarbc_tiles() -> None:
    """The ArcGIS query is normalised into a tile record."""
    requested: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request)
        return httpx.Response(200, json=_lidarbc_payload())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        tiles = discover_lidarbc_tiles(BBOX, client=client, page_size=10)
    assert len(tiles) == 1
    tile = tiles[0]
    assert tile.tile_id == "092g024_2_3_4"
    assert tile.year == 2016
    assert tile.density == 8.0
    assert tile.bbox == (-123.30, 49.20, -123.10, 49.32)
    assert requested[0].url.params["f"] == "geojson"


def test_discover_lidarbc_rejects_invalid_bbox() -> None:
    """A reversed or out-of-range box is refused before a request."""
    with pytest.raises(ValueError, match="longitude"):
        discover_lidarbc_tiles((0.0, 0.0, 0.0, 1.0))


def test_discover_canelevation_tiles(tmp_path: Path) -> None:
    """The CanElevation GeoPackage index is filtered by bbox, provider, and project."""
    index = tmp_path / "tiles.geojson"
    frame = gpd.GeoDataFrame(
        {
            "Provider": ["BC", "BC", "ON"],
            "Project": ["Lower_Mainland_2016", "Other", "Lower_Mainland_2016"],
            "Tile_name": ["bc_092g024_2_3_4", "bc_092g025_1_1_1", "on_tile"],
            "URL": [
                "https://example.test/bc_092g024_2_3_4_utm10_20170714.copc.laz",
                "https://example.test/bc_092g025_1_1_1_utm10_20170714.copc.laz",
                "https://example.test/on_tile.copc.laz",
            ],
        },
        geometry=[Point(-123.25, 49.26), Point(-122.80, 49.20), Point(-80.0, 45.0)],
        crs="EPSG:4326",
    )
    frame.to_file(index, driver="GeoJSON")
    tiles = discover_canelevation_tiles(index, BBOX, project="Lower_Mainland_2016", provider="BC")
    assert len(tiles) == 1
    tile = tiles[0]
    assert tile.source == "canelevation"
    assert tile.year == 2016
    assert tile.projection == "utm10"
    assert tile.bbox[0] == pytest.approx(-123.25)
    assert discover_canelevation_tiles(index, BBOX, provider="ON") == ()
    assert discover_canelevation_tiles(index, BBOX, limit=1)[0].tile_id.startswith("bc_")
    with pytest.raises(FileNotFoundError):
        discover_canelevation_tiles(tmp_path / "missing.gpkg", BBOX)


def test_tile_manifest_round_trip(tmp_path: Path) -> None:
    """A manifest survives JSON and converts to a GeoJSON footprint."""
    tile = LidarTile(
        source="lidarbc",
        tile_id="tile",
        filename="tile.laz",
        url="https://example.test/tile.laz",
        year=2024,
        projection="utm10",
        density=8.0,
        bbox=(-123.3, 49.2, -123.1, 49.3),
        metadata_url="https://example.test/report.pdf",
        notes="test",
    )
    manifest = make_manifest("lidarbc", BBOX, [tile])
    path = write_tile_manifest(manifest, tmp_path / "manifest.json")
    restored = read_tile_manifest(path)
    assert restored.tiles[0] == tile
    geojson = tiles_to_geojson(restored)
    assert geojson["type"] == "FeatureCollection"
    features = geojson["features"]
    assert isinstance(features, list)
    assert features[0]["properties"]["tile_id"] == "tile"


def test_read_manifest_rejects_malformed_payload(tmp_path: Path) -> None:
    """A payload without a tile list is refused."""
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"tiles": "no"}), encoding="utf-8")
    with pytest.raises(ValueError, match="tiles list"):
        read_tile_manifest(path)


def test_download_tiles_reuses_an_existing_file(tmp_path: Path) -> None:
    """An existing non-empty tile is reused and hashed instead of re-downloaded."""
    tile = LidarTile(
        source="lidarbc",
        tile_id="tile",
        filename="tile.laz",
        url="https://example.test/tile.laz",
        year=None,
        projection="",
        density=None,
        bbox=(0.0, 0.0, 1.0, 1.0),
    )
    target = tmp_path / "lidarbc" / "tile.laz"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"payload")
    records = download_tiles([tile], tmp_path)
    assert len(records) == 1
    assert records[0].status == "verified"
    assert records[0].message == "reused existing file"
    assert records[0].size_bytes == 7
