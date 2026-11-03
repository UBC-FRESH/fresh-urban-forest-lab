"""Repeat-measures canopy change between two aligned canopy-height grids.

The comparison is deliberately threshold-based: a cell is canopy when its height is at
least ``threshold_m``. Gain, loss, and stable canopy are reported in square metres and as
a share of the earlier canopy. The module also reports mean height change inside the
stable canopy so a user can separate cover change from growth.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class CanopyChange:
    """A repeat-measures canopy-change summary.

    Attributes
    ----------
    threshold_m : float
        Canopy threshold in metres.
    earlier_canopy_m2 : float
        Earlier canopy area.
    later_canopy_m2 : float
        Later canopy area.
    gain_m2 : float
        Area that became canopy.
    loss_m2 : float
        Area that stopped being canopy.
    stable_m2 : float
        Area that was canopy in both dates.
    net_m2 : float
        Later minus earlier canopy area.
    gain_pct_of_earlier : float
        Gain as a percentage of earlier canopy.
    loss_pct_of_earlier : float
        Loss as a percentage of earlier canopy.
    mean_height_change_m : float
        Mean later-minus-earlier height on stable canopy cells.
    """

    threshold_m: float
    earlier_canopy_m2: float
    later_canopy_m2: float
    gain_m2: float
    loss_m2: float
    stable_m2: float
    net_m2: float
    gain_pct_of_earlier: float
    loss_pct_of_earlier: float
    mean_height_change_m: float


def canopy_change(
    earlier: NDArray[np.float32] | NDArray[np.float64],
    later: NDArray[np.float32] | NDArray[np.float64],
    *,
    threshold_m: float = 2.0,
    cell_area_m2: float = 1.0,
) -> CanopyChange:
    """Compare two aligned canopy-height grids.

    Parameters
    ----------
    earlier : numpy.ndarray
        Earlier canopy height in metres.
    later : numpy.ndarray
        Later canopy height in metres.
    threshold_m : float
        Minimum height counted as canopy.
    cell_area_m2 : float
        Area represented by one cell.

    Returns
    -------
    CanopyChange
        Area and height-change summary.

    Raises
    ------
    ValueError
        When the grids do not share a shape.
    """
    first = np.asarray(earlier, dtype=np.float64)
    second = np.asarray(later, dtype=np.float64)
    if first.shape != second.shape:
        raise ValueError("earlier and later canopy grids must share a shape")
    valid = np.isfinite(first) & np.isfinite(second)
    earlier_mask = valid & (first >= threshold_m)
    later_mask = valid & (second >= threshold_m)
    gain = int(np.count_nonzero(later_mask & ~earlier_mask))
    loss = int(np.count_nonzero(earlier_mask & ~later_mask))
    stable = int(np.count_nonzero(earlier_mask & later_mask))
    earlier_area = int(np.count_nonzero(earlier_mask)) * cell_area_m2
    later_area = int(np.count_nonzero(later_mask)) * cell_area_m2
    height_change = (
        float(np.mean(second[earlier_mask & later_mask] - first[earlier_mask & later_mask]))
        if stable
        else 0.0
    )
    return CanopyChange(
        threshold_m=threshold_m,
        earlier_canopy_m2=round(earlier_area, 3),
        later_canopy_m2=round(later_area, 3),
        gain_m2=round(gain * cell_area_m2, 3),
        loss_m2=round(loss * cell_area_m2, 3),
        stable_m2=round(stable * cell_area_m2, 3),
        net_m2=round(later_area - earlier_area, 3),
        gain_pct_of_earlier=round(100.0 * gain * cell_area_m2 / earlier_area, 3)
        if earlier_area
        else 0.0,
        loss_pct_of_earlier=round(100.0 * loss * cell_area_m2 / earlier_area, 3)
        if earlier_area
        else 0.0,
        mean_height_change_m=round(height_change, 3),
    )


def change_grid(
    earlier: NDArray[np.float32] | NDArray[np.float64],
    later: NDArray[np.float32] | NDArray[np.float64],
    *,
    threshold_m: float = 2.0,
) -> NDArray[np.int8]:
    """Build a raster change class grid.

    Parameters
    ----------
    earlier : numpy.ndarray
        Earlier canopy height in metres.
    later : numpy.ndarray
        Later canopy height in metres.
    threshold_m : float
        Minimum height counted as canopy.

    Returns
    -------
    numpy.ndarray
        ``-1`` for loss, ``1`` for gain, and ``0`` for stable or non-canopy.

    Raises
    ------
    ValueError
        When the grids do not share a shape.
    """
    first = np.asarray(earlier, dtype=np.float64)
    second = np.asarray(later, dtype=np.float64)
    if first.shape != second.shape:
        raise ValueError("earlier and later canopy grids must share a shape")
    valid = np.isfinite(first) & np.isfinite(second)
    earlier_mask = valid & (first >= threshold_m)
    later_mask = valid & (second >= threshold_m)
    result = np.zeros(first.shape, dtype=np.int8)
    result[later_mask & ~earlier_mask] = 1
    result[earlier_mask & ~later_mask] = -1
    return result
