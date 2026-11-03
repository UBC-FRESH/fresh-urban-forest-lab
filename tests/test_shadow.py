"""Tests for the projected shadow kernel."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np

from fresh_urban_forest.models import TreeRecord
from fresh_urban_forest.shadow import cast_shadows, shadow_mask_png
from tests.fixtures import make_dataset


def _dataset(tmp_path: Path) -> object:
    """Build the synthetic dataset."""
    return make_dataset(tmp_path)


def test_shadow_masks_are_separable_and_non_empty(tmp_path: Path) -> None:
    """Buildings and trees produce separate masks that union into the combined mask."""
    dataset = make_dataset(tmp_path)
    when = dt.datetime(2026, 6, 21, 19, 0, tzinfo=dt.UTC)
    masks = cast_shadows(dataset, when, include_terrain=False)
    assert masks.building.any()
    assert masks.tree.any()
    assert np.array_equal(masks.combined, masks.building | masks.tree | masks.terrain)
    assert masks.building_count >= 1
    assert masks.tree_count >= 1
    assert masks.solar.is_daylight


def test_night_has_no_direct_shadows(tmp_path: Path) -> None:
    """Below the horizon the kernel returns empty direct-shadow masks."""
    dataset = make_dataset(tmp_path)
    when = dt.datetime(2026, 6, 21, 7, 0, tzinfo=dt.UTC)
    masks = cast_shadows(dataset, when, include_terrain=False)
    assert not masks.solar.is_daylight
    assert not masks.combined.any()
    assert masks.tree_count == 0
    assert masks.building_count == 0


def test_excluding_a_tree_reduces_the_tree_mask(tmp_path: Path) -> None:
    """Marginal-shade mode removes exactly one contributing crown."""
    dataset = make_dataset(tmp_path)
    tree = dataset.trees[1]
    when = dt.datetime(2026, 6, 21, 19, 0, tzinfo=dt.UTC)
    full = cast_shadows(dataset, when, include_terrain=False)
    without = cast_shadows(dataset, when, include_terrain=False, exclude_tree_id=tree.tree_id)
    assert without.tree_count == full.tree_count - 1
    assert int(without.tree.sum()) <= int(full.tree.sum())


def test_shadow_png_modes(tmp_path: Path) -> None:
    """Every documented mode returns a valid PNG."""
    dataset = make_dataset(tmp_path)
    masks = cast_shadows(
        dataset,
        dt.datetime(2026, 6, 21, 19, 0, tzinfo=dt.UTC),
        include_terrain=False,
    )
    assert shadow_mask_png(masks, mode="combined").startswith(b"\x89PNG")
    assert shadow_mask_png(masks, mode="building").startswith(b"\x89PNG")
    assert shadow_mask_png(masks, mode="tree").startswith(b"\x89PNG")
    assert shadow_mask_png(masks, mode="terrain").startswith(b"\x89PNG")


def test_terrain_mask_adds_shadow_on_a_small_grid(tmp_path: Path) -> None:
    """The terrain-horizon branch is exercised on a small flat grid."""
    dataset = make_dataset(tmp_path)
    masks = cast_shadows(
        dataset,
        dt.datetime(2026, 6, 21, 19, 0, tzinfo=dt.UTC),
        include_terrain=True,
    )
    assert masks.terrain.shape == (dataset.terrain.height, dataset.terrain.width)
    assert masks.terrain_included is False
    assert isinstance(dataset.trees[0], TreeRecord)


def test_low_sun_casts_a_longer_building_shadow(tmp_path: Path) -> None:
    """A low sun produces a larger building mask than a near-overhead sun."""
    dataset = make_dataset(tmp_path)
    low = cast_shadows(
        dataset,
        dt.datetime(2026, 6, 21, 15, 0, tzinfo=dt.UTC),
        include_terrain=False,
    )
    high = cast_shadows(
        dataset,
        dt.datetime(2026, 6, 21, 19, 0, tzinfo=dt.UTC),
        include_terrain=False,
    )
    assert low.solar.altitude_deg < high.solar.altitude_deg
    assert int(low.building.sum()) > int(high.building.sum())


def test_target_height_reduces_building_shadow(tmp_path: Path) -> None:
    """A higher target plane shortens the projected building shadow."""
    dataset = make_dataset(tmp_path)
    when = dt.datetime(2026, 6, 21, 15, 0, tzinfo=dt.UTC)
    ground = cast_shadows(dataset, when, target_height_m=0.1, include_terrain=False)
    roof = cast_shadows(dataset, when, target_height_m=8.0, include_terrain=False)
    assert int(ground.building.sum()) >= int(roof.building.sum())
