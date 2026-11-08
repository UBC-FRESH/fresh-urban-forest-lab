"""Sensitivity of a LiDAR canopy-change product to a height offset.

The module applies a vertical shift to the earlier canopy surface and recomputes
the thresholded change metrics. It is a screening sensitivity, not a field
validation or a substitute for survey-grade vertical control.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from fresh_urban_forest.change import CanopyChange, canopy_change
from fresh_urban_forest.evidence import evidence

SENSITIVITY_EVIDENCE = evidence(
    "scenario",
    "height-offset-sensitivity",
    uncertainty=(
        "The offset range is a sensitivity envelope, not a measured vertical error. "
        "It does not capture classification, co-registration, or scale effects."
    ),
    source="P43 2 m citywide change grid and P41/P43 scale comparison.",
)


@dataclass(frozen=True, slots=True)
class OffsetResult:
    """Change metrics at one height offset.

    Attributes
    ----------
    offset_m : float
        Offset applied to the earlier canopy height.
    metrics : CanopyChange
        Recomputed change metrics.
    """

    offset_m: float
    metrics: CanopyChange

    def to_dict(self) -> dict[str, object]:
        """Convert the result to a JSON-safe mapping.

        Returns
        -------
        dict
            Offset and change metrics.
        """
        values = asdict(self.metrics)
        return {
            "offset_m": self.offset_m,
            "metrics": {key: round(float(value), 3) for key, value in values.items()},
        }


def offset_sensitivity(
    earlier: NDArray[np.floating],
    later: NDArray[np.floating],
    valid: NDArray[np.bool_],
    *,
    offsets_m: Sequence[float] = (-1.0, -0.5, 0.0, 0.5, 1.0),
    threshold_m: float = 2.0,
    cell_area_m2: float = 4.0,
) -> tuple[OffsetResult, ...]:
    """Recompute change metrics across a sequence of earlier-height offsets.

    Parameters
    ----------
    earlier : numpy.ndarray
        Earlier canopy height.
    later : numpy.ndarray
        Later canopy height.
    valid : numpy.ndarray
        Valid comparison mask.
    offsets_m : sequence of float
        Offsets added to the earlier height.
    threshold_m : float
        Canopy threshold.
    cell_area_m2 : float
        Area of one raster cell.

    Returns
    -------
    tuple of OffsetResult
        One result per offset, in input order.

    Raises
    ------
    ValueError
        When shapes differ or no offsets are supplied.
    """
    first = np.asarray(earlier, dtype=np.float64)
    second = np.asarray(later, dtype=np.float64)
    observed = np.asarray(valid, dtype=np.bool_)
    if not (first.shape == second.shape == observed.shape) or first.ndim != 2:
        raise ValueError("earlier, later, and valid must share a 2-D shape")
    if not offsets_m:
        raise ValueError("at least one offset is required")
    results: list[OffsetResult] = []
    for offset in offsets_m:
        shifted = np.where(observed, first + float(offset), np.nan)
        target = np.where(observed, second, np.nan)
        results.append(
            OffsetResult(
                offset_m=float(offset),
                metrics=canopy_change(
                    shifted,
                    target,
                    threshold_m=threshold_m,
                    cell_area_m2=cell_area_m2,
                ),
            )
        )
    return tuple(results)


def summarize_sensitivity(results: Sequence[OffsetResult]) -> dict[str, object]:
    """Summarize the net and height-change range across offsets.

    Parameters
    ----------
    results : sequence of OffsetResult
        Sensitivity results.

    Returns
    -------
    dict
        Net range, sign stability, and method evidence.
    """
    if not results:
        raise ValueError("at least one result is required")
    nets = [result.metrics.net_m2 for result in results]
    heights = [result.metrics.mean_height_change_m for result in results]
    signs = {1 if value > 0 else -1 if value < 0 else 0 for value in nets}
    return {
        "offset_min_m": min(result.offset_m for result in results),
        "offset_max_m": max(result.offset_m for result in results),
        "net_min_m2": min(nets),
        "net_max_m2": max(nets),
        "net_range_m2": max(nets) - min(nets),
        "net_signs": sorted(signs),
        "net_sign_stable": len(signs) == 1,
        "height_min_m": min(heights),
        "height_max_m": max(heights),
        "evidence": SENSITIVITY_EVIDENCE.to_dict(),
    }


def write_sensitivity(
    results: Sequence[OffsetResult],
    summary: dict[str, object],
    out_dir: Path,
    *,
    stem: str = "change_sensitivity",
) -> Path:
    """Write the sensitivity JSON.

    Parameters
    ----------
    results : sequence of OffsetResult
        Sensitivity results.
    summary : dict
        Summary from :func:`summarize_sensitivity`.
    out_dir : Path
        Destination directory.
    stem : str
        Output stem.

    Returns
    -------
    Path
        Written JSON path.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "fresh-urban-forest.change-sensitivity.v1",
        "summary": summary,
        "results": [result.to_dict() for result in results],
    }
    path = out_dir / f"{stem}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


__all__ = [
    "SENSITIVITY_EVIDENCE",
    "OffsetResult",
    "offset_sensitivity",
    "summarize_sensitivity",
    "write_sensitivity",
]
