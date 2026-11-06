"""Helpers for provisional Lower Mainland city model instances.

The three P34 instances mix source types: a public tree inventory (Surrey), an explicit
LiDAR DEM/DSM pair (Burnaby), and Metro Vancouver land-cover classes (Coquitlam). These
helpers keep the coordinate, class, and summary rules in one testable place.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import distance_transform_edt, maximum_filter

from fresh_urban_forest.allometry import is_native_species, species_group
from fresh_urban_forest.models import TreeRecord

LCC_CONIFER = 6
LCC_DECIDUOUS = 7
LCC_SHRUB = 8
LCC_WATER = 12
LCC_CONIFER_PAVED = 15
LCC_DECIDUOUS_PAVED = 16
TREE_CLASSES = frozenset({LCC_CONIFER, LCC_DECIDUOUS, LCC_CONIFER_PAVED, LCC_DECIDUOUS_PAVED})


@dataclass(frozen=True, slots=True)
class GridSpec:
    """A north-up projected grid.

    Attributes
    ----------
    left : float
        Left edge in the projected CRS.
    top : float
        Top edge in the projected CRS.
    resolution_m : float
        Cell size in metres.
    width : int
        Number of columns.
    height : int
        Number of rows.
    """

    left: float
    top: float
    resolution_m: float
    width: int
    height: int

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """Return ``(left, bottom, right, top)``.

        Returns
        -------
        tuple of float
            Projected bounds.
        """
        return (
            self.left,
            self.top - self.height * self.resolution_m,
            self.left + self.width * self.resolution_m,
            self.top,
        )


def grid_for_bounds(
    bounds: tuple[float, float, float, float],
    *,
    resolution_m: float,
) -> GridSpec:
    """Build an outward-rounded north-up grid over projected bounds.

    Parameters
    ----------
    bounds : tuple of float
        ``(left, bottom, right, top)``.
    resolution_m : float
        Cell size in metres.

    Returns
    -------
    GridSpec
        Grid covering the bounds.
    """
    if resolution_m <= 0:
        raise ValueError("resolution_m must be positive")
    left = np.floor(bounds[0] / resolution_m) * resolution_m
    bottom = np.floor(bounds[1] / resolution_m) * resolution_m
    right = np.ceil(bounds[2] / resolution_m) * resolution_m
    top = np.ceil(bounds[3] / resolution_m) * resolution_m
    return GridSpec(
        left=float(left),
        top=float(top),
        resolution_m=float(resolution_m),
        width=max(1, round((right - left) / resolution_m)),
        height=max(1, round((top - bottom) / resolution_m)),
    )


def class_canopy_height(class_code: int) -> float:
    """Return a screening canopy height for a Metro LCC class.

    Parameters
    ----------
    class_code : int
        Metro Vancouver LCC 2020 class code.

    Returns
    -------
    float
        Canopy height in metres, or zero for non-tree classes.
    """
    if class_code in {LCC_CONIFER, LCC_CONIFER_PAVED}:
        return 16.0
    if class_code in {LCC_DECIDUOUS, LCC_DECIDUOUS_PAVED}:
        return 12.0
    if class_code == LCC_SHRUB:
        return 4.0
    return 0.0


def class_species(class_code: int) -> str:
    """Return a transparent land-cover label for a tree class.

    Parameters
    ----------
    class_code : int
        Metro Vancouver LCC 2020 class code.

    Returns
    -------
    str
        Species-like label, or an empty string for non-tree classes.
    """
    if class_code in {LCC_CONIFER, LCC_CONIFER_PAVED}:
        return "Coniferous (LCC 2020)"
    if class_code in {LCC_DECIDUOUS, LCC_DECIDUOUS_PAVED}:
        return "Deciduous (LCC 2020)"
    if class_code == LCC_SHRUB:
        return "Shrub (LCC 2020)"
    return ""


def canopy_records_from_classes(
    classes: NDArray[np.uint8],
    grid: GridSpec,
    *,
    step_m: float = 20.0,
    source: str = "metro_lcc_2020",
) -> tuple[TreeRecord, ...]:
    """Place canopy candidates at local canopy-distance maxima.

    This deliberately avoids a fixed sampling grid. It uses the distance transform of the
    land-cover tree mask and a deterministic non-maximum suppression pass so positions
    follow canopy shape rather than a square lattice.

    Parameters
    ----------
    classes : numpy.ndarray
        LCC class grid.
    grid : GridSpec
        Grid definition for ``classes``.
    step_m : float
        Minimum candidate spacing in metres.
    source : str
        Source identifier written to each record.

    Returns
    -------
    tuple of TreeRecord
        Canopy candidates. These are not individual-tree observations.
    """
    from fresh_urban_forest.terrain import unproject_xy

    tree_mask = np.isin(classes, list(TREE_CLASSES))
    if not np.any(tree_mask):
        return ()
    distance = distance_transform_edt(tree_mask)
    window = max(3, round(step_m / grid.resolution_m))
    local_maxima = maximum_filter(distance, size=window)
    peaks = np.argwhere(tree_mask & (distance == local_maxima) & (distance >= 1.0))
    if len(peaks) == 0:
        return ()
    peak_distances = distance[peaks[:, 0], peaks[:, 1]]
    order = np.argsort(-peak_distances, kind="stable")
    peak_xy = np.column_stack(
        (
            grid.left + (peaks[:, 1] + 0.5) * grid.resolution_m,
            grid.top - (peaks[:, 0] + 0.5) * grid.resolution_m,
        )
    )
    spacing = step_m * 0.7
    kept: list[int] = []
    occupied: dict[tuple[int, int], list[int]] = {}
    for index in order:
        x = float(peak_xy[index, 0])
        y = float(peak_xy[index, 1])
        cell = (int(np.floor(x / spacing)), int(np.floor(y / spacing)))
        too_close = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for other in occupied.get((cell[0] + dx, cell[1] + dy), []):
                    if np.hypot(x - peak_xy[other, 0], y - peak_xy[other, 1]) < spacing:
                        too_close = True
                        break
                if too_close:
                    break
            if too_close:
                break
        if too_close:
            continue
        kept.append(int(index))
        occupied.setdefault(cell, []).append(int(index))
    records: list[TreeRecord] = []
    for index in kept:
        row, col = peaks[index]
        code = int(classes[row, col])
        x = float(peak_xy[index, 0])
        y = float(peak_xy[index, 1])
        lon, lat = unproject_xy(x, y, "EPSG:3157")
        height = class_canopy_height(code)
        group = species_group(class_species(code))
        records.append(
            TreeRecord(
                tree_id=f"{source}:{len(records) + 1:07d}",
                lon=lon,
                lat=lat,
                species=class_species(code),
                common_name="Canopy candidate",
                genus="",
                height_m=height,
                crown_width_m=10.0 if group == "conifer" else 8.0,
                crown_ratio=0.55,
                status="alive",
                source=source,
                source_date="2020",
                native=None,
                x_m=x,
                y_m=y,
                attributes={
                    "height_measured": "false",
                    "crown_width_measured": "false",
                    "species_measured": "false",
                    "canopy_candidate": "true",
                },
            )
        )
    return tuple(records)


def tree_inventory_summary(
    trees: tuple[TreeRecord, ...],
    *,
    source_rows: int | None = None,
) -> dict[str, object]:
    """Build a compact inventory summary for a provisional city instance.

    Parameters
    ----------
    trees : tuple of TreeRecord
        Enriched tree records.
    source_rows : int or None
        Source row count, defaulting to the record count.

    Returns
    -------
    dict
        Fields consumed by the city app's completeness panel.
    """
    heights = [tree.height_m for tree in trees if tree.height_m is not None and tree.height_m > 0.5]
    dbhs = [tree.dbh_cm for tree in trees if tree.dbh_cm is not None and tree.dbh_cm > 0.5]
    measured = {
        "dbh": sum(1 for tree in trees if tree.attributes.get("dbh_measured") == "true"),
        "height": sum(1 for tree in trees if tree.attributes.get("height_measured") == "true"),
        "crown_width": sum(
            1 for tree in trees if tree.attributes.get("crown_width_measured") == "true"
        ),
        "species": sum(1 for tree in trees if tree.attributes.get("species_measured") == "true"),
    }
    species = [tree.species or tree.common_name or "Unknown" for tree in trees]
    return {
        "source_rows": source_rows if source_rows is not None else len(trees),
        "mapped_rows": len(trees),
        "unmapped_rows": max(0, (source_rows or len(trees)) - len(trees)),
        "dbh_outliers": 0,
        "height_outliers": 0,
        "height_non_null": len(heights),
        "height_median_m": round(float(np.median(heights)), 3) if heights else 0.0,
        "height_p95_m": round(float(np.percentile(heights, 95)), 3) if heights else 0.0,
        "dbh_non_null": len(dbhs),
        "dbh_median_cm": round(float(np.median(dbhs)), 3) if dbhs else 0.0,
        "species_count": len({value for value in species if value != "Unknown"}),
        "native_fraction": round(
            sum(1 for tree in trees if tree.native) / max(1, len(trees)),
            4,
        ),
        "local_area_count": 1,
        "measured_species": measured["species"],
        "measured_dbh": measured["dbh"],
        "measured_height": measured["height"],
        "measured_crown_width": measured["crown_width"],
        "height_comparison": {"overall": {"n": 0}},
        "completeness": {
            "total": len(trees),
            "fields": {
                key: {
                    "label": label,
                    "measured": measured[key],
                    "total": len(trees),
                    "fraction": round(measured[key] / max(1, len(trees)), 4),
                }
                for key, label in (
                    ("dbh", "DBH"),
                    ("height", "Height"),
                    ("crown_width", "Crown width"),
                    ("species", "Species"),
                )
            },
        },
    }


def is_native_label(species: str) -> bool:
    """Return the native flag for a species label.

    Parameters
    ----------
    species : str
        Species or common name.

    Returns
    -------
    bool
        Native flag.
    """
    return is_native_species(species)
