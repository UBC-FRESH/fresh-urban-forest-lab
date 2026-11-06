"""Tests for orthophoto tile geometry helpers."""

from __future__ import annotations

from pathlib import Path

from fresh_urban_forest.imagery import TileSource, vancouver_2022_source


def test_web_mercator_tile_and_pixel_coordinates() -> None:
    """Known Vancouver coordinates map to the expected zoom-19 tile."""
    source = TileSource(
        name="test",
        service_url="https://example.invalid/MapServer",
        zoom=19,
        cache_dir=Path("unused"),
    )
    x, y = source.tile_bounds(-123.029477, 49.27354)
    assert (x, y) == (82969, 179443)
    assert source.tile_url(x, y).endswith("/tile/19/179443/82969")
    assert source.tile_path(x, y).name == "179443.jpg"


def test_vancouver_source_is_public_zoom_19() -> None:
    """The prepared Vancouver source uses the public orthophoto service."""
    source = vancouver_2022_source(Path("data/tmp/imagery_test"))
    assert source.zoom == 19
    assert "Orthophotos_2022" in source.service_url
    assert source.name == "vancouver_2022_orthophoto"
