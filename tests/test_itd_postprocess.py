"""Tests for opt-in CHM/ITD crown post-processing."""

from __future__ import annotations

import math

import pytest

from fresh_urban_forest.itd import DetectedTree
from fresh_urban_forest.itd_postprocess import postprocess_trees


def _tree(
    tree_id: str,
    x: float,
    y: float,
    *,
    height_m: float = 10.0,
    crown_radius_m: float = 2.0,
) -> DetectedTree:
    """Build a compact DetectedTree fixture.

    Parameters
    ----------
    tree_id : str
        Identifier.
    x, y : float
        Projected coordinates.
    height_m : float
        Crown height.
    crown_radius_m : float
        Equivalent crown radius.

    Returns
    -------
    DetectedTree
        Fixture tree.
    """
    area = math.pi * crown_radius_m**2
    return DetectedTree(
        tree_id=tree_id,
        row=0,
        col=0,
        height_m=height_m,
        crown_radius_m=crown_radius_m,
        crown_area_m2=area,
        x=x,
        y=y,
        lon=x,
        lat=y,
    )


def test_buffer_flags_trees_near_the_edge() -> None:
    """Only crowns within the edge buffer are flagged."""
    trees = (
        _tree("center", 50.0, 50.0),
        _tree("west", 2.0, 50.0),
        _tree("north", 50.0, 98.0),
    )
    result = postprocess_trees(trees, (0.0, 0.0, 100.0, 100.0), buffer_m=5.0)
    assert result.buffer_ids == ("north", "west")
    assert [tree.tree_id for tree in result.kept()] == ["center"]


def test_small_tree_flags_are_strictly_below_the_threshold() -> None:
    """A crown exactly at the height threshold is not flagged."""
    trees = (
        _tree("small", 50.0, 50.0, height_m=1.5),
        _tree("edge", 60.0, 50.0, height_m=2.0),
        _tree("tall", 70.0, 50.0, height_m=3.0),
    )
    result = postprocess_trees(
        trees,
        (0.0, 0.0, 100.0, 100.0),
        buffer_m=0.0,
        max_small_height_m=2.0,
    )
    assert result.small_ids == ("small",)
    assert {tree.tree_id for tree in result.kept()} == {"edge", "tall"}


def test_overlapping_small_crown_merges_into_larger() -> None:
    """A much smaller, height-similar overlapping crown is merged."""
    trees = (
        _tree("large", 50.0, 50.0, height_m=10.0, crown_radius_m=3.0),
        _tree("small", 51.0, 50.0, height_m=9.5, crown_radius_m=1.0),
        _tree("far", 80.0, 80.0, height_m=10.0, crown_radius_m=2.0),
    )
    result = postprocess_trees(trees, (0.0, 0.0, 100.0, 100.0), buffer_m=0.0)
    assert result.merge_groups == (("large", "small"),)
    assert len(result.trees) == 2
    merged = next(tree for tree in result.trees if tree.tree_id == "large")
    assert merged.crown_area_m2 == pytest.approx(math.pi * 3.0**2 + math.pi * 1.0**2)
    assert merged.height_m == pytest.approx(10.0)
    assert merged.crown_radius_m == pytest.approx(math.sqrt((math.pi * 9.0 + math.pi) / math.pi))


def test_large_height_difference_prevents_merge() -> None:
    """Overlapping crowns with very different heights are not merged."""
    trees = (
        _tree("large", 50.0, 50.0, height_m=10.0, crown_radius_m=3.0),
        _tree("small", 51.0, 50.0, height_m=5.0, crown_radius_m=1.0),
    )
    result = postprocess_trees(trees, (0.0, 0.0, 100.0, 100.0), buffer_m=0.0)
    assert result.merge_groups == ()
    assert len(result.trees) == 2


def test_similar_area_prevents_merge() -> None:
    """Two similar-sized overlapping crowns are left alone."""
    trees = (
        _tree("first", 50.0, 50.0, height_m=10.0, crown_radius_m=3.0),
        _tree("second", 51.0, 50.0, height_m=9.5, crown_radius_m=2.5),
    )
    result = postprocess_trees(trees, (0.0, 0.0, 100.0, 100.0), buffer_m=0.0)
    assert result.merge_groups == ()
    assert len(result.trees) == 2


def test_merge_can_be_disabled() -> None:
    """The merge path is opt-out."""
    trees = (
        _tree("large", 50.0, 50.0, height_m=10.0, crown_radius_m=3.0),
        _tree("small", 51.0, 50.0, height_m=9.5, crown_radius_m=1.0),
    )
    result = postprocess_trees(
        trees,
        (0.0, 0.0, 100.0, 100.0),
        buffer_m=0.0,
        merge=False,
    )
    assert result.merge_groups == ()
    assert len(result.trees) == 2
    assert "over-segmentation merge disabled" in result.warnings


def test_empty_trees_return_a_warning() -> None:
    """An empty crown set returns empty lists and a warning."""
    result = postprocess_trees((), (0.0, 0.0, 100.0, 100.0))
    assert result.trees == ()
    assert result.buffer_ids == ()
    assert result.small_ids == ()
    assert result.warnings == ("no detected trees",)


def test_invalid_parameters_raise() -> None:
    """Invalid bounds and thresholds fail clearly."""
    trees = (_tree("one", 50.0, 50.0),)
    with pytest.raises(ValueError, match="bounds"):
        postprocess_trees(trees, (100.0, 0.0, 0.0, 100.0))
    with pytest.raises(ValueError, match="buffer_m"):
        postprocess_trees(trees, (0.0, 0.0, 100.0, 100.0), buffer_m=-1.0)
    with pytest.raises(ValueError, match="max_small_height_m"):
        postprocess_trees(trees, (0.0, 0.0, 100.0, 100.0), max_small_height_m=-1.0)
    with pytest.raises(ValueError, match="merge_max_area_ratio"):
        postprocess_trees(trees, (0.0, 0.0, 100.0, 100.0), merge_max_area_ratio=1.0)


def test_result_is_json_friendly() -> None:
    """The summary is JSON-serializable and reports kept IDs."""
    result = postprocess_trees(
        (_tree("edge", 1.0, 50.0), _tree("center", 50.0, 50.0)),
        (0.0, 0.0, 100.0, 100.0),
        buffer_m=5.0,
    )
    payload = result.to_dict()
    assert payload["tree_count"] == 2
    assert payload["buffer_ids"] == ["edge"]
    assert payload["kept_ids"] == ["center"]


def test_group_extent_guard_blocks_a_chain_merge() -> None:
    """A chain that would grow past the group extent is stopped."""
    trees = (
        _tree("a", 0.0, 0.0, height_m=10.0, crown_radius_m=20.0),
        _tree("b", 15.0, 0.0, height_m=10.0, crown_radius_m=10.0),
        _tree("c", 25.0, 0.0, height_m=10.0, crown_radius_m=5.0),
    )
    result = postprocess_trees(
        trees,
        (-50.0, -50.0, 50.0, 50.0),
        buffer_m=0.0,
        merge_max_group_extent_m=20.0,
    )
    assert result.merge_groups == (("a", "b"),)
    assert {tree.tree_id for tree in result.trees} == {"a", "c"}


def test_group_member_guard_limits_group_size() -> None:
    """No merge group exceeds the member cap."""
    trees = (
        _tree("a", 0.0, 0.0, height_m=10.0, crown_radius_m=20.0),
        _tree("b", 5.0, 0.0, height_m=10.0, crown_radius_m=5.0),
        _tree("c", 10.0, 0.0, height_m=10.0, crown_radius_m=5.0),
    )
    result = postprocess_trees(
        trees,
        (-50.0, -50.0, 50.0, 50.0),
        buffer_m=0.0,
        merge_max_group_members=2,
    )
    assert all(len(group) <= 2 for group in result.merge_groups)


def test_invalid_group_guards_raise() -> None:
    """Group-size and extent guards reject invalid values."""
    trees = (_tree("one", 0.0, 0.0),)
    with pytest.raises(ValueError, match="merge_max_group_members"):
        postprocess_trees(
            trees,
            (-10.0, -10.0, 10.0, 10.0),
            merge_max_group_members=1,
        )
    with pytest.raises(ValueError, match="merge_max_group_extent_m"):
        postprocess_trees(
            trees,
            (-10.0, -10.0, 10.0, 10.0),
            merge_max_group_extent_m=0.0,
        )


def test_absorbed_crown_cannot_become_an_anchor() -> None:
    """A small crown absorbed by a large crown cannot then absorb another crown."""
    trees = (
        _tree("a", 0.0, 0.0, height_m=10.0, crown_radius_m=20.0),
        _tree("b", 15.0, 0.0, height_m=10.0, crown_radius_m=10.0),
        _tree("c", 25.0, 0.0, height_m=10.0, crown_radius_m=5.0),
    )
    result = postprocess_trees(
        trees,
        (-50.0, -50.0, 50.0, 50.0),
        buffer_m=0.0,
        merge_max_group_extent_m=100.0,
    )
    assert result.merge_groups == (("a", "b"),)
    assert {tree.tree_id for tree in result.trees} == {"a", "c"}


def test_anchor_absorbs_multiple_small_crowns() -> None:
    """One anchor can absorb several small crowns within the caps."""
    trees = (
        _tree("anchor", 0.0, 0.0, height_m=10.0, crown_radius_m=20.0),
        _tree("one", 5.0, 0.0, height_m=10.0, crown_radius_m=5.0),
        _tree("two", 10.0, 0.0, height_m=10.0, crown_radius_m=5.0),
    )
    result = postprocess_trees(
        trees,
        (-50.0, -50.0, 50.0, 50.0),
        buffer_m=0.0,
        merge_max_group_members=3,
    )
    assert result.merge_groups == (("anchor", "one", "two"),)
    assert len(result.trees) == 1


def test_synthetic_audit_patch_merges_split_crown_only() -> None:
    """A known split crown merges; two similar distinct crowns do not."""
    trees = (
        _tree("true-left", 50.0, 50.0, height_m=12.0, crown_radius_m=4.0),
        _tree("true-right", 52.0, 50.0, height_m=11.5, crown_radius_m=2.0),
        _tree("distinct-left", 80.0, 50.0, height_m=10.0, crown_radius_m=3.0),
        _tree("distinct-right", 84.0, 50.0, height_m=10.0, crown_radius_m=2.8),
        _tree("far", 20.0, 20.0, height_m=10.0, crown_radius_m=2.0),
    )
    result = postprocess_trees(trees, (0.0, 0.0, 100.0, 100.0), buffer_m=0.0)
    assert result.merge_groups == (("true-left", "true-right"),)
    assert {tree.tree_id for tree in result.trees} == {
        "true-left",
        "distinct-left",
        "distinct-right",
        "far",
    }
