"""Inventory completeness summaries.

The UBC inventory is location-rich and attribute-poor. This module makes the measured
share of DBH, height, crown width, and species explicit so a canopy or carbon number can
be read with its evidence.
"""

from __future__ import annotations

from collections.abc import Sequence

from fresh_urban_forest.models import TreeRecord

FIELDS: tuple[tuple[str, str], ...] = (
    ("dbh", "DBH"),
    ("height", "Height"),
    ("crown_width", "Crown width"),
    ("species", "Species"),
)


def inventory_completeness(trees: Sequence[TreeRecord]) -> dict[str, object]:
    """Calculate the measured share of the key tree attributes.

    Parameters
    ----------
    trees : sequence of TreeRecord
        Tree population. Removed and dead trees are excluded.

    Returns
    -------
    dict
        ``total`` live trees and a ``fields`` mapping with measured counts and fractions.
    """
    live = [tree for tree in trees if tree.status not in {"removed", "dead"}]
    total = len(live)
    fields: dict[str, dict[str, object]] = {}
    for key, label in FIELDS:
        measured = sum(1 for tree in live if _measured(tree, key))
        fields[key] = {
            "label": label,
            "measured": measured,
            "total": total,
            "fraction": round(measured / total, 4) if total else 0.0,
        }
    return {"total": total, "fields": fields}


def _measured(tree: TreeRecord, key: str) -> bool:
    """Return whether a field was measured rather than imputed.

    Parameters
    ----------
    tree : TreeRecord
        Tree to inspect.
    key : str
        Field key, such as ``dbh``.

    Returns
    -------
    bool
        ``True`` when the source flag says measured, or when no flag exists and the value
        is present.
    """
    flag = tree.attributes.get(f"{key}_measured")
    if flag is not None:
        return flag.strip().lower() in {"true", "1", "yes"}
    if key == "dbh":
        return tree.dbh_cm is not None
    if key == "height":
        return tree.height_m is not None
    if key == "crown_width":
        return tree.crown_width_m is not None
    return bool(tree.species)
