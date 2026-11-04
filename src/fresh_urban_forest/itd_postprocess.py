"""Opt-in post-processing for CHM-detected tree crowns.

The CHM detector returns local-maxima crowns. This module adds three conservative,
deterministic post-processing steps:

- flag crowns whose centroid is inside a rectangular edge buffer;
- flag crowns below a height threshold;
- merge a much smaller overlapping crown into a larger anchor crown when their heights are
  similar, with no transitive chains.

It does not change ``detect_trees`` and it is not a point-cloud instance-segmentation
resolver. The merge rule is deliberately conservative and records every source ID.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

from fresh_urban_forest.itd import DetectedTree


@dataclass(frozen=True, slots=True)
class TreePostprocessResult:
    """Post-processed crowns and their exclusion flags.

    Attributes
    ----------
    trees : tuple of DetectedTree
        Crowns after conservative merging.
    buffer_ids : tuple of str
        Representative IDs inside the edge buffer.
    small_ids : tuple of str
        Representative IDs below the small-tree height threshold.
    merge_groups : tuple of tuple of str
        Source-ID groups that were merged. Each group has two or more IDs.
    warnings : tuple of str
        Non-fatal warnings.
    """

    trees: tuple[DetectedTree, ...]
    buffer_ids: tuple[str, ...]
    small_ids: tuple[str, ...]
    merge_groups: tuple[tuple[str, ...], ...] = ()
    warnings: tuple[str, ...] = ()

    def kept(self) -> tuple[DetectedTree, ...]:
        """Return crowns that are neither buffer-flagged nor small-tree-flagged.

        Returns
        -------
        tuple of DetectedTree
            Crowns that pass both flags.
        """
        excluded = set(self.buffer_ids) | set(self.small_ids)
        return tuple(tree for tree in self.trees if tree.tree_id not in excluded)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly summary.

        Returns
        -------
        dict
            Counts, ID lists, groups, and kept IDs.
        """
        return {
            "tree_count": len(self.trees),
            "buffer_ids": list(self.buffer_ids),
            "small_ids": list(self.small_ids),
            "merge_groups": [list(group) for group in self.merge_groups],
            "kept_ids": [tree.tree_id for tree in self.kept()],
            "warnings": list(self.warnings),
        }


def _validate_bounds(bounds: tuple[float, float, float, float]) -> None:
    """Validate a rectangular XY bounds tuple.

    Parameters
    ----------
    bounds : tuple of float
        ``(xmin, ymin, xmax, ymax)``.

    Raises
    ------
    ValueError
        When the bounds are reversed or non-finite.
    """
    xmin, ymin, xmax, ymax = bounds
    values = (xmin, ymin, xmax, ymax)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("bounds must be finite")
    if xmin >= xmax or ymin >= ymax:
        raise ValueError("bounds must satisfy xmin < xmax and ymin < ymax")


def _merge_groups(
    trees: tuple[DetectedTree, ...],
    *,
    max_height_delta_m: float,
    max_area_ratio: float,
    max_group_members: int,
    max_group_extent_m: float,
) -> list[list[int]]:
    """Return non-transitive anchor groups for conservative crown merges.

    Only a larger crown can act as an anchor. An absorbed crown cannot become an anchor
    and absorb another crown, so a chain cannot propagate across the dataset. Anchors are
    processed from largest to smallest area.

    Parameters
    ----------
    trees : tuple of DetectedTree
        Input crowns.
    max_height_delta_m : float
        Maximum absolute height difference for a merge.
    max_area_ratio : float
        Maximum smaller/larger crown-area ratio for a merge.
    max_group_members : int
        Maximum number of source crowns in one merge group.
    max_group_extent_m : float
        Maximum XY bounding-box diagonal of one merge group.

    Returns
    -------
    list of list of int
        Groups with two or more indices, ordered by anchor tree ID.
    """
    order = sorted(
        range(len(trees)),
        key=lambda index: (
            -trees[index].crown_area_m2,
            -trees[index].height_m,
            trees[index].tree_id,
        ),
    )
    assigned: set[int] = set()
    groups: list[list[int]] = []

    for anchor_index in order:
        if anchor_index in assigned:
            continue
        anchor = trees[anchor_index]
        assigned.add(anchor_index)
        group = [anchor_index]
        candidates: list[tuple[float, float, int]] = []
        for index, candidate in enumerate(trees):
            if index == anchor_index or index in assigned:
                continue
            if candidate.crown_area_m2 > anchor.crown_area_m2 * max_area_ratio:
                continue
            if abs(candidate.height_m - anchor.height_m) > max_height_delta_m:
                continue
            distance = math.hypot(anchor.x - candidate.x, anchor.y - candidate.y)
            if distance > anchor.crown_radius_m:
                continue
            candidates.append((distance, candidate.crown_area_m2, index))
        candidates.sort()
        for _, _, index in candidates:
            if len(group) >= max_group_members:
                break
            xs = [trees[member].x for member in group] + [trees[index].x]
            ys = [trees[member].y for member in group] + [trees[index].y]
            extent = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
            if extent > max_group_extent_m:
                continue
            group.append(index)
            assigned.add(index)
        if len(group) > 1:
            groups.append(group)

    groups.sort(key=lambda group: trees[group[0]].tree_id)
    return groups


def _merge_group(trees: tuple[DetectedTree, ...], group: list[int]) -> DetectedTree:
    """Merge one group into a representative crown.

    Parameters
    ----------
    trees : tuple of DetectedTree
        Input crowns.
    group : list of int
        Indices in the group.

    Returns
    -------
    DetectedTree
        Representative crown with summed area, maximum height, and area-weighted centre.
    """
    members = [trees[index] for index in group]
    representative = max(
        members, key=lambda tree: (tree.crown_area_m2, tree.height_m, tree.tree_id)
    )
    total_area = sum(tree.crown_area_m2 for tree in members)
    total_weight = sum(tree.crown_area_m2 for tree in members)
    if total_weight > 0:
        x = sum(tree.x * tree.crown_area_m2 for tree in members) / total_weight
        y = sum(tree.y * tree.crown_area_m2 for tree in members) / total_weight
        lon = sum(tree.lon * tree.crown_area_m2 for tree in members) / total_weight
        lat = sum(tree.lat * tree.crown_area_m2 for tree in members) / total_weight
    else:
        x = sum(tree.x for tree in members) / len(members)
        y = sum(tree.y for tree in members) / len(members)
        lon = sum(tree.lon for tree in members) / len(members)
        lat = sum(tree.lat for tree in members) / len(members)
    return replace(
        representative,
        height_m=max(tree.height_m for tree in members),
        crown_radius_m=math.sqrt(total_area / math.pi),
        crown_area_m2=total_area,
        x=x,
        y=y,
        lon=lon,
        lat=lat,
    )


def postprocess_trees(
    trees: tuple[DetectedTree, ...],
    bounds: tuple[float, float, float, float],
    *,
    buffer_m: float = 10.0,
    max_small_height_m: float = 2.0,
    merge: bool = True,
    merge_max_height_delta_m: float = 2.0,
    merge_max_area_ratio: float = 0.6,
    merge_max_group_members: int = 4,
    merge_max_group_extent_m: float = 30.0,
) -> TreePostprocessResult:
    """Flag and conservatively merge CHM-detected crowns.

    Parameters
    ----------
    trees : tuple of DetectedTree
        Crowns from ``detect_trees``.
    bounds : tuple of float
        Rectangular XY bounds ``(xmin, ymin, xmax, ymax)`` for the edge buffer.
    buffer_m : float, optional
        Edge-buffer width in metres. The default is ``10.0``. Must be non-negative.
    max_small_height_m : float, optional
        Crowns strictly below this height are flagged as small. The default is ``2.0``.
        Must be non-negative.
    merge : bool, optional
        Whether to run the conservative merge. The default is ``True``.
    merge_max_height_delta_m : float, optional
        Maximum absolute height difference for a merge. The default is ``2.0``.
    merge_max_area_ratio : float, optional
        Maximum smaller/larger crown-area ratio for a merge. The default is ``0.6``.
    merge_max_group_members : int, optional
        Maximum source crowns in one merge group. The default is ``4``. Must be at least
        ``2``.
    merge_max_group_extent_m : float, optional
        Maximum XY bounding-box diagonal of one merge group. The default is ``30.0``.
        Must be positive.

    Returns
    -------
    TreePostprocessResult
        Merged crowns, buffer/small flags, merge groups, and warnings.

    Raises
    ------
    ValueError
        When bounds, buffer, height, or merge parameters are invalid.

    Notes
    -----
    The merge rule is intentionally conservative: the smaller crown's centroid must fall
    inside the larger crown's equivalent radius, the height difference must be small, and
    the smaller crown must be much smaller by area. The merge is non-transitive: only a
    larger crown can anchor, and an absorbed crown cannot absorb another crown. Group-size
    and group-extent caps provide a second guard. It is not a general instance segmentation
    method and does not use the point cloud.
    """
    if buffer_m < 0:
        raise ValueError("buffer_m must be non-negative")
    if max_small_height_m < 0:
        raise ValueError("max_small_height_m must be non-negative")
    if merge_max_height_delta_m < 0:
        raise ValueError("merge_max_height_delta_m must be non-negative")
    if not 0 < merge_max_area_ratio < 1:
        raise ValueError("merge_max_area_ratio must be between 0 and 1")
    if merge_max_group_members < 2:
        raise ValueError("merge_max_group_members must be at least 2")
    if merge_max_group_extent_m <= 0:
        raise ValueError("merge_max_group_extent_m must be positive")
    _validate_bounds(bounds)

    warnings: list[str] = []
    if not trees:
        return TreePostprocessResult(
            trees=(),
            buffer_ids=(),
            small_ids=(),
            warnings=("no detected trees",),
        )

    merged_trees: list[DetectedTree] = []
    merge_groups: list[tuple[str, ...]] = []
    if merge:
        groups = _merge_groups(
            trees,
            max_height_delta_m=merge_max_height_delta_m,
            max_area_ratio=merge_max_area_ratio,
            max_group_members=merge_max_group_members,
            max_group_extent_m=merge_max_group_extent_m,
        )
        merged_indices: set[int] = set()
        for group in groups:
            merged_indices.update(group)
            merged_trees.append(_merge_group(trees, group))
            merge_groups.append(tuple(sorted(trees[index].tree_id for index in group)))
        for index, tree in enumerate(trees):
            if index not in merged_indices:
                merged_trees.append(tree)
        merged_trees.sort(key=lambda tree: tree.tree_id)
        if merge_groups:
            warnings.append(f"merged {len(merge_groups)} over-segmentation groups")
    else:
        merged_trees = list(trees)
        warnings.append("over-segmentation merge disabled")

    xmin, ymin, xmax, ymax = bounds
    buffer_ids = tuple(
        tree.tree_id
        for tree in merged_trees
        if (
            tree.x - xmin <= buffer_m
            or xmax - tree.x <= buffer_m
            or tree.y - ymin <= buffer_m
            or ymax - tree.y <= buffer_m
        )
    )
    small_ids = tuple(tree.tree_id for tree in merged_trees if tree.height_m < max_small_height_m)
    if buffer_m * 2 >= min(xmax - xmin, ymax - ymin):
        warnings.append("buffer is at least half the shorter bounds dimension")

    return TreePostprocessResult(
        trees=tuple(merged_trees),
        buffer_ids=buffer_ids,
        small_ids=small_ids,
        merge_groups=tuple(merge_groups),
        warnings=tuple(warnings),
    )
