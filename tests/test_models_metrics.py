"""Tests for the serialisable contracts and canopy metrics."""

from __future__ import annotations

from collections import Counter

import pytest

from fresh_urban_forest.metrics import (
    SIZE_CLASSES,
    compare_metrics,
    compute_metrics,
    shannon_index,
    size_class,
)
from fresh_urban_forest.models import (
    CanopyMetrics,
    Scenario,
    ScenarioEdit,
    TreeRecord,
    edit_from_dict,
    edit_to_dict,
    metrics_from_dict,
    metrics_to_dict,
    scenario_from_dict,
    scenario_to_dict,
    tree_from_dict,
    tree_to_dict,
)


def _tree(index: int, *, species: str = "Acer rubrum", native: bool = False) -> TreeRecord:
    """Build a deterministic tree for metric tests."""
    return TreeRecord(
        tree_id=f"t{index}",
        lon=-123.25 + index * 0.0001,
        lat=49.26,
        species=species,
        common_name=species,
        dbh_cm=10.0 + index * 5,
        height_m=8.0 + index,
        crown_width_m=3.0 + index * 0.2,
        crown_ratio=0.5,
        native=native,
        status="alive",
    )


def test_tree_round_trip_preserves_optional_values() -> None:
    """A tree survives a JSON dictionary round trip."""
    tree = _tree(1)
    payload = tree_to_dict(tree)
    restored = tree_from_dict(payload)
    assert restored == tree
    assert restored.label == "Acer rubrum"


def test_tree_from_dict_handles_blank_and_invalid_values() -> None:
    """Blank optional values become ``None`` and unknown statuses become alive."""
    restored = tree_from_dict(
        {
            "tree_id": "x",
            "lon": "-123.25",
            "lat": 49.26,
            "dbh_cm": "",
            "height_m": "not-a-number",
            "status": "mystery",
        }
    )
    assert restored.dbh_cm is None
    assert restored.height_m is None
    assert restored.status == "alive"
    assert restored.lon == -123.25


def test_metrics_round_trip() -> None:
    """Metrics survive a dictionary round trip."""
    metrics = compute_metrics(
        [_tree(1), _tree(2, species="Thuja plicata", native=True)], area_ha=1.0
    )
    restored = metrics_from_dict(metrics_to_dict(metrics))
    assert restored.tree_count == metrics.tree_count
    assert restored.species_composition == metrics.species_composition


def test_edit_and_scenario_round_trip() -> None:
    """Scenario edits and scenarios survive a dictionary round trip."""
    edit = ScenarioEdit(
        edit_id="e1",
        kind="plant",
        tree_id="p1",
        lon=-123.25,
        lat=49.26,
        species="Acer macrophyllum",
        dbh_cm=6.0,
        note="test",
    )
    assert edit_from_dict(edit_to_dict(edit)) == edit
    scenario = Scenario(
        scenario_id="s1",
        name="Test",
        created_utc="2026-11-03T00:00:00Z",
        base_dataset_id="d1",
        years=10,
        edits=(edit,),
        revision=2,
    )
    assert scenario_from_dict(scenario_to_dict(scenario)) == scenario


def test_edit_from_dict_rejects_unknown_kind() -> None:
    """An unknown edit kind is refused rather than silently defaulted."""
    with pytest.raises(ValueError, match="unknown edit kind"):
        edit_from_dict({"edit_id": "e", "kind": "explode", "tree_id": "t"})


def test_size_classes_cover_the_expected_edges() -> None:
    """Diameter classes are ordered and map edge values correctly."""
    assert size_class(None) == "unknown"
    assert size_class(5) == "0-10"
    assert size_class(10) == "10-20"
    assert size_class(85) == "80+"
    assert SIZE_CLASSES[0][0] == "0-10"


def test_shannon_index_is_zero_for_one_species() -> None:
    """A single species has zero diversity."""
    assert shannon_index(Counter({"Acer": 4})) == 0.0
    assert shannon_index(Counter()) == 0.0
    assert shannon_index(Counter({"Acer": 2, "Thuja": 2})) > 0.0


def test_compute_metrics_filters_removed_trees_and_uses_offsets() -> None:
    """Dead trees are excluded and offsets reconcile tree metrics with a raster."""
    trees = [_tree(1), _tree(2), _tree(3)]
    trees.append(TreeRecord(tree_id="dead", lon=0.0, lat=0.0, status="removed"))
    metrics = compute_metrics(trees, area_ha=1.0, cover_offset=20.0, volume_offset=1000.0)
    assert metrics.tree_count == 3
    assert metrics.canopy_cover_pct > 20.0
    assert metrics.canopy_volume_m3 > 1000.0
    assert sum(count for _, count in metrics.size_classes) == 3


def test_compare_metrics_reports_absolute_and_relative_change() -> None:
    """Comparison reports deltas and zero-safe relative changes."""
    before = compute_metrics([_tree(1)], area_ha=1.0)
    after = compute_metrics([_tree(1), _tree(2)], area_ha=1.0)
    comparison = compare_metrics(before, after)
    assert comparison["tree_count_delta"] == 1.0
    assert comparison["canopy_cover_delta_pct"] > 0
    zero = compare_metrics(
        CanopyMetrics(0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        CanopyMetrics(0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    )
    assert zero["canopy_cover_relative_pct"] == 0.0
