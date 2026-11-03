"""Canopy and composition metrics for a tree population.

The functions are pure and deterministic. Raster cover and volume can be passed in when a
CHM is available; otherwise the functions fall back to crown geometry so a scenario can
still be compared before a LiDAR product is attached.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence

import numpy as np

from fresh_urban_forest.allometry import tree_carbon_kg, tree_crown_volume_m3
from fresh_urban_forest.models import CanopyMetrics, TreeRecord

SIZE_CLASSES: tuple[tuple[str, float, float], ...] = (
    ("0-10", 0.0, 10.0),
    ("10-20", 10.0, 20.0),
    ("20-30", 20.0, 30.0),
    ("30-50", 30.0, 50.0),
    ("50-80", 50.0, 80.0),
    ("80+", 80.0, float("inf")),
)


def size_class(dbh_cm: float | None) -> str:
    """Return the diameter class label for a tree.

    Parameters
    ----------
    dbh_cm : float or None
        Diameter at breast height in centimetres.

    Returns
    -------
    str
        A label such as ``10-20``.
    """
    if dbh_cm is None:
        return "unknown"
    for label, lower, upper in SIZE_CLASSES:
        if lower <= dbh_cm < upper:
            return label
    return "80+"


def compute_metrics(
    trees: Sequence[TreeRecord],
    *,
    area_ha: float,
    canopy_cover_pct_value: float | None = None,
    canopy_volume_m3_value: float | None = None,
    cover_offset: float = 0.0,
    volume_offset: float = 0.0,
) -> CanopyMetrics:
    """Calculate composition and canopy metrics for a tree population.

    Parameters
    ----------
    trees : sequence of TreeRecord
        Trees to summarise. Removed and dead trees are excluded.
    area_ha : float
        Analysis area in hectares, used for the crown-area cover fallback.
    canopy_cover_pct_value : float or None
        Raster-derived canopy cover. When omitted, cover is estimated from crown area.
    canopy_volume_m3_value : float or None
        Raster-derived canopy volume. When omitted, cover is estimated from crown volume.
    cover_offset : float
        Additive offset applied to the crown-area cover estimate. Scenario projections
        use this to reconcile the tree inventory with the wider raster canopy.
    volume_offset : float
        Additive offset applied to the crown-volume estimate.

    Returns
    -------
    CanopyMetrics
        The metrics.
    """
    live = [tree for tree in trees if tree.status not in {"removed", "dead"}]
    heights = [tree.height_m for tree in live if tree.height_m is not None and tree.height_m > 0]
    dbhs = [tree.dbh_cm for tree in live if tree.dbh_cm is not None and tree.dbh_cm > 0]
    species_labels = [tree.species or tree.common_name or "Unknown" for tree in live]
    species_counts = Counter(species_labels)
    native_count = sum(1 for tree in live if tree.native)
    crown_area_m2 = sum(
        math.pi / 4.0 * tree.crown_width_m**2
        for tree in live
        if tree.crown_width_m is not None and tree.crown_width_m > 0
    )
    tree_cover = 100.0 * crown_area_m2 / max(area_ha * 10_000.0, 1.0)
    cover = (
        float(canopy_cover_pct_value)
        if canopy_cover_pct_value is not None
        else min(100.0, max(0.0, tree_cover + cover_offset))
    )
    tree_volume = sum(tree_crown_volume_m3(tree) for tree in live)
    volume = (
        float(canopy_volume_m3_value)
        if canopy_volume_m3_value is not None
        else max(0.0, tree_volume + volume_offset)
    )
    size_counts = Counter(size_class(dbh) for dbh in dbhs)
    ordered_sizes = tuple((label, size_counts.get(label, 0)) for label, _, _ in SIZE_CLASSES)
    return CanopyMetrics(
        tree_count=len(live),
        species_count=len([label for label in species_counts if label != "Unknown"]),
        native_fraction=(native_count / len(live)) if live else 0.0,
        canopy_cover_pct=round(cover, 3),
        canopy_volume_m3=round(float(volume), 3),
        mean_height_m=round(float(np.mean(heights)), 3) if heights else 0.0,
        p95_height_m=round(float(np.percentile(heights, 95)), 3) if heights else 0.0,
        total_carbon_kg=round(sum(tree_carbon_kg(tree) for tree in live), 3),
        shannon_index=round(shannon_index(species_counts), 4),
        size_classes=ordered_sizes,
        species_composition=tuple(species_counts.most_common(30)),
    )


def shannon_index(counts: Counter[str]) -> float:
    """Calculate the Shannon diversity index.

    Parameters
    ----------
    counts : Counter
        Counts by species label.

    Returns
    -------
    float
        Shannon index in natural-log units.
    """
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    return -sum((count / total) * math.log(count / total) for count in counts.values() if count > 0)


def compare_metrics(before: CanopyMetrics, after: CanopyMetrics) -> dict[str, float]:
    """Calculate absolute and relative change between two metric snapshots.

    Parameters
    ----------
    before : CanopyMetrics
        Baseline.
    after : CanopyMetrics
        Scenario outcome.

    Returns
    -------
    dict of str to float
        Differences for count, cover, volume, height, carbon, diversity, and native share.
    """
    return {
        "tree_count_delta": float(after.tree_count - before.tree_count),
        "canopy_cover_delta_pct": round(after.canopy_cover_pct - before.canopy_cover_pct, 3),
        "canopy_volume_delta_m3": round(after.canopy_volume_m3 - before.canopy_volume_m3, 3),
        "mean_height_delta_m": round(after.mean_height_m - before.mean_height_m, 3),
        "carbon_delta_kg": round(after.total_carbon_kg - before.total_carbon_kg, 3),
        "shannon_delta": round(after.shannon_index - before.shannon_index, 4),
        "native_fraction_delta": round(after.native_fraction - before.native_fraction, 4),
        "canopy_cover_relative_pct": _relative(after.canopy_cover_pct, before.canopy_cover_pct),
        "canopy_volume_relative_pct": _relative(after.canopy_volume_m3, before.canopy_volume_m3),
    }


def _relative(after: float, before: float) -> float:
    """Calculate a percentage change with a zero-safe denominator.

    Parameters
    ----------
    after : float
        New value.
    before : float
        Old value.

    Returns
    -------
    float
        Percentage change, or zero when the old value is zero.
    """
    if abs(before) < 1e-9:
        return 0.0
    return round(100.0 * (after - before) / before, 3)
