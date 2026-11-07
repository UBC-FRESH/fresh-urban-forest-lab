"""Tests for Surrey candidate image-scoring helpers."""

from __future__ import annotations

from score_surrey_imagery import _chunk_key, _sigmoid


def test_sigmoid_is_bounded() -> None:
    """The probability transform is monotone and bounded."""
    assert _sigmoid(0) == 0.5
    assert 0 < _sigmoid(-20) < 0.5
    assert 0.5 < _sigmoid(20) < 1


def test_chunk_key_uses_bounds_and_margin() -> None:
    """Points map into stable image chunks."""
    bounds = (0.0, 0.0, 10_000.0, 10_000.0)
    assert _chunk_key(1100.0, 8900.0, bounds) == (1, 1)
    assert _chunk_key(2100.0, 8900.0, bounds) == (2, 1)
    assert _chunk_key(1100.0, 6900.0, bounds) == (1, 3)
