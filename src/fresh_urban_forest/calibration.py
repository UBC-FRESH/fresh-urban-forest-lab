"""Local allometric calibration from measured inventory trees.

The first calibration is a height-diameter power law fitted by species group. It is a
local check on the generic profiles, not an annual growth model; annual growth still needs
repeat measurements of the same trees.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from fresh_urban_forest.allometry import species_group
from fresh_urban_forest.models import TreeRecord

CALIBRATION_SCHEMA_VERSION = "fresh-urban-forest.allometry.v1"


@dataclass(frozen=True, slots=True)
class HeightDiameterFit:
    """A fitted height-diameter power law.

    Attributes
    ----------
    group : str
        Species group.
    coefficient : float
        Multiplier in ``height = 1.3 + coefficient * dbh ** exponent``.
    exponent : float
        Exponent in the power law.
    sample_size : int
        Number of measured trees used.
    rmse_m : float
        Root-mean-square error in metres.
    r2 : float
        Coefficient of determination on the original scale.
    dbh_min_cm : float
        Minimum fitted DBH.
    dbh_max_cm : float
        Maximum fitted DBH.
    """

    group: str
    coefficient: float
    exponent: float
    sample_size: int
    rmse_m: float
    r2: float
    dbh_min_cm: float
    dbh_max_cm: float


def fit_height_diameter(
    trees: Sequence[TreeRecord],
    group: str,
    *,
    min_samples: int = 20,
) -> HeightDiameterFit | None:
    """Fit a height-diameter power law for one species group.

    Parameters
    ----------
    trees : sequence of TreeRecord
        Inventory trees.
    group : str
        Species group name.
    min_samples : int
        Minimum number of measured trees.

    Returns
    -------
    HeightDiameterFit or None
        The fit, or ``None`` when there are too few measured trees.
    """
    samples = [
        tree
        for tree in trees
        if tree.status not in {"removed", "dead"}
        and tree.dbh_cm is not None
        and tree.height_m is not None
        and tree.dbh_cm > 0
        and tree.height_m > 1.4
        and species_group(tree.species or tree.common_name) == group
        and _measured(tree, "dbh")
        and _measured(tree, "height")
    ]
    if len(samples) < min_samples:
        return None
    dbh = np.asarray([float(tree.dbh_cm) for tree in samples if tree.dbh_cm is not None])
    height = np.asarray([float(tree.height_m) for tree in samples if tree.height_m is not None])
    x = np.log(dbh)
    y = np.log(np.maximum(height - 1.3, 0.1))
    exponent, intercept = np.polyfit(x, y, 1)
    coefficient = float(np.exp(intercept))
    predicted = 1.3 + coefficient * dbh**exponent
    residuals = height - predicted
    rmse = float(np.sqrt(np.mean(residuals**2)))
    total = float(np.sum((height - np.mean(height)) ** 2))
    r2 = 1.0 - float(np.sum(residuals**2)) / total if total > 0 else 0.0
    return HeightDiameterFit(
        group=group,
        coefficient=round(coefficient, 6),
        exponent=round(float(exponent), 6),
        sample_size=len(samples),
        rmse_m=round(rmse, 3),
        r2=round(r2, 4),
        dbh_min_cm=round(float(np.min(dbh)), 2),
        dbh_max_cm=round(float(np.max(dbh)), 2),
    )


def fit_allometry(
    trees: Sequence[TreeRecord],
    *,
    min_samples: int = 20,
) -> dict[str, HeightDiameterFit]:
    """Fit height-diameter curves for every species group with enough data.

    Parameters
    ----------
    trees : sequence of TreeRecord
        Inventory trees.
    min_samples : int
        Minimum measured trees per group.

    Returns
    -------
    dict of str to HeightDiameterFit
        Fits by group.
    """
    fits: dict[str, HeightDiameterFit] = {}
    for group in ("conifer", "deciduous", "unknown"):
        fit = fit_height_diameter(trees, group, min_samples=min_samples)
        if fit is not None:
            fits[group] = fit
    return fits


def write_allometry(fits: dict[str, HeightDiameterFit], path: Path) -> Path:
    """Write allometric fits as JSON.

    Parameters
    ----------
    fits : dict of str to HeightDiameterFit
        Fits to write.
    path : Path
        Destination JSON.

    Returns
    -------
    Path
        The written path.
    """
    payload = {
        "schema_version": CALIBRATION_SCHEMA_VERSION,
        "method": "log-log fit of height - 1.3 against DBH, by species group",
        "fits": {group: asdict(fit) for group, fit in fits.items()},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _measured(tree: TreeRecord, key: str) -> bool:
    """Return whether a field was measured.

    Parameters
    ----------
    tree : TreeRecord
        Tree to inspect.
    key : str
        Field key.

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
    return tree.height_m is not None
