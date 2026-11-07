"""Tests for full-resolution image buffer handling."""

from __future__ import annotations

import pytest

from fresh_urban_forest.imagery import band_sequential_rgb


def test_band_sequential_rgb_restores_pixel_order() -> None:
    """GDAL BSQ bytes become HWC RGB pixels."""
    # 2x2 image: band 1 has 1,2,3,4; band 2 has 11,12,13,14; band 3 has 21,22,23,24.
    payload = bytes([1, 2, 3, 4, 11, 12, 13, 14, 21, 22, 23, 24])
    image = band_sequential_rgb(payload, 2, 2)
    assert image.shape == (2, 2, 3)
    assert image[0, 0].tolist() == [1, 11, 21]
    assert image[1, 1].tolist() == [4, 14, 24]


def test_band_sequential_rgb_rejects_wrong_length() -> None:
    """A non-three-band buffer is rejected."""
    with pytest.raises(ValueError, match="expected 12 bytes"):
        band_sequential_rgb(b"\x00" * 11, 2, 2)
