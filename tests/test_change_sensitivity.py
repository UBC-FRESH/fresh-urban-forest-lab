"""Tests for the height-offset sensitivity calculation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import numpy as np
import pytest

from fresh_urban_forest.change_sensitivity import (
    offset_sensitivity,
    summarize_sensitivity,
    write_sensitivity,
)


def _arrays() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return a small change fixture."""
    earlier = np.full((2, 2), 2.5, dtype=np.float32)
    later = np.full((2, 2), 2.0, dtype=np.float32)
    valid = np.ones((2, 2), dtype=np.bool_)
    return earlier, later, valid


def test_offset_sensitivity_tracks_sign_change() -> None:
    """A negative offset can remove earlier canopy, changing the net sign."""
    earlier, later, valid = _arrays()
    results = offset_sensitivity(
        earlier,
        later,
        valid,
        offsets_m=(-1.0, 0.0, 1.0),
        threshold_m=2.0,
        cell_area_m2=1.0,
    )
    assert len(results) == 3
    assert results[0].metrics.earlier_canopy_m2 == pytest.approx(0.0)
    assert results[1].metrics.earlier_canopy_m2 == pytest.approx(4.0)
    summary = summarize_sensitivity(results)
    assert summary["net_sign_stable"] is False
    assert cast(float, summary["net_min_m2"]) <= 0.0
    assert cast(float, summary["net_max_m2"]) > 0.0


def test_offset_sensitivity_rejects_bad_inputs() -> None:
    """Mismatched shapes and an empty offset list are rejected."""
    earlier, later, valid = _arrays()
    with pytest.raises(ValueError, match="share a 2-D shape"):
        offset_sensitivity(earlier, later, np.ones((3, 2), dtype=np.bool_))
    with pytest.raises(ValueError, match="at least one offset"):
        offset_sensitivity(earlier, later, valid, offsets_m=())


def test_write_sensitivity(tmp_path: Path) -> None:
    """The sensitivity JSON contains summary and results."""
    earlier, later, valid = _arrays()
    results = offset_sensitivity(earlier, later, valid, offsets_m=(-1.0, 0.0))
    path = write_sensitivity(results, summarize_sensitivity(results), tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "fresh-urban-forest.change-sensitivity.v1"
    assert len(payload["results"]) == 2
