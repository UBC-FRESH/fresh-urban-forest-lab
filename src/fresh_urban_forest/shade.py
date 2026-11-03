"""Time-integrated shade accounting and marginal tree contribution.

A shadow at noon is not a shade service. This module accumulates building, tree, and
terrain masks over a daylight period, separates overlap from each source, and computes the
additional shade caused by one tree. The result is a planning surface, not a temperature
or cooling measurement.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import itertools
import json
import statistics
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from fresh_urban_forest.allometry import tree_crown_volume_m3
from fresh_urban_forest.evidence import Evidence, evidence
from fresh_urban_forest.models import TreeRecord, UrbanForestDataset
from fresh_urban_forest.shadow import cast_shadows
from fresh_urban_forest.solar import daylight_hours

SHADE_EVIDENCE = evidence(
    "physics",
    "projected-shadow-accumulation",
    uncertainty=(
        "2.5-D crown ellipses, no penumbra or leaf transmissivity; terrain horizon is "
        "coarse and only evaluated for small grids."
    ),
    source="NOAA solar position + projected building/tree silhouettes",
)


@dataclass(frozen=True, slots=True)
class ShadePeriod:
    """Aggregated shade over a set of daylight samples.

    Attributes
    ----------
    whens : tuple of datetime.datetime
        Sample times.
    step_hours : float
        Hours represented by each sample.
    target_height_m : float
        Height above ground of the target plane.
    daylight_samples : int
        Number of sample times with the sun above the horizon.
    daylight_sampled_hours : float
        Sampled daylight hours.
    sunlit_hours : numpy.ndarray
        Hours each cell is directly sunlit.
    building_shade_hours : numpy.ndarray
        Hours each cell is shaded by a building.
    tree_shade_hours : numpy.ndarray
        Hours each cell is shaded by any tree.
    terrain_shade_hours : numpy.ndarray
        Hours each cell is shaded by the terrain horizon.
    combined_shade_hours : numpy.ndarray
        Hours each cell is shaded by at least one source.
    overlap_hours : numpy.ndarray
        Hours each cell is shaded by both a building and a tree.
    marginal_tree_shade_hours : numpy.ndarray
        Additional shade caused by the selected tree, or by all trees when no tree is named.
    metrics : mapping of str to float
        Period fractions and estimates.
    image_version : str
        Content hash for cache-busting.
    evidence : Evidence
        Method and tier.
    """

    whens: tuple[dt.datetime, ...]
    step_hours: float
    target_height_m: float
    daylight_samples: int
    daylight_sampled_hours: float
    sunlit_hours: NDArray[np.float32]
    building_shade_hours: NDArray[np.float32]
    tree_shade_hours: NDArray[np.float32]
    terrain_shade_hours: NDArray[np.float32]
    combined_shade_hours: NDArray[np.float32]
    overlap_hours: NDArray[np.float32]
    marginal_tree_shade_hours: NDArray[np.float32]
    metrics: dict[str, float]
    image_version: str
    evidence: Evidence

    @property
    def width(self) -> int:
        """Return the grid width.

        Returns
        -------
        int
            Number of columns.
        """
        return int(self.sunlit_hours.shape[1])

    @property
    def height(self) -> int:
        """Return the grid height.

        Returns
        -------
        int
            Number of rows.
        """
        return int(self.sunlit_hours.shape[0])

    def to_dict(self) -> dict[str, object]:
        """Convert the summary to a JSON-safe dictionary.

        Returns
        -------
        dict
            Period, metrics, evidence, and image version.
        """
        return {
            "times": [value.isoformat() for value in self.whens],
            "step_hours": self.step_hours,
            "target_height_m": self.target_height_m,
            "daylight_samples": self.daylight_samples,
            "daylight_sampled_hours": self.daylight_sampled_hours,
            "metrics": self.metrics,
            "image_version": self.image_version,
            "evidence": self.evidence.to_dict(),
        }


def default_step_hours(whens: tuple[dt.datetime, ...]) -> float:
    """Infer the sample interval from a sorted time sequence.

    Parameters
    ----------
    whens : tuple of datetime.datetime
        Sample times.

    Returns
    -------
    float
        Median interval in hours, or one hour for a single sample.
    """
    if len(whens) < 2:
        return 1.0
    differences = [
        (second - first).total_seconds() / 3600.0 for first, second in itertools.pairwise(whens)
    ]
    return max(0.1, float(statistics.median(differences)))


def shade_period(
    dataset: UrbanForestDataset,
    whens: tuple[dt.datetime, ...],
    *,
    target_height_m: float = 1.5,
    step_hours: float | None = None,
    include_terrain: bool = True,
    tree_id: str | None = None,
) -> ShadePeriod:
    """Accumulate shade over a sequence of times.

    Parameters
    ----------
    dataset : UrbanForestDataset
        Dataset with trees, buildings, and terrain.
    whens : tuple of datetime.datetime
        Sample times, normally in chronological order.
    target_height_m : float
        Height above ground of the target plane.
    step_hours : float or None
        Hours represented by each sample. Inferred from the times when omitted.
    include_terrain : bool
        Include the coarse terrain horizon.
    tree_id : str or None
        Compute marginal shade for one tree. When omitted, the marginal layer is all
        tree shade that is not under a building or terrain shadow.

    Returns
    -------
    ShadePeriod
        Aggregated arrays, metrics, and evidence.
    """
    ordered = tuple(sorted(whens))
    step = default_step_hours(ordered) if step_hours is None else max(0.1, step_hours)
    grid = dataset.terrain
    shape = (grid.height, grid.width)
    sunlit = np.zeros(shape, dtype=np.float64)
    building = np.zeros(shape, dtype=np.float64)
    tree = np.zeros(shape, dtype=np.float64)
    terrain = np.zeros(shape, dtype=np.float64)
    combined = np.zeros(shape, dtype=np.float64)
    overlap = np.zeros(shape, dtype=np.float64)
    marginal = np.zeros(shape, dtype=np.float64)
    daylight_dates: dict[dt.date, float] = {}
    daylight_samples = 0
    solar_altitudes: list[float] = []
    for when in ordered:
        masks = cast_shadows(
            dataset,
            when,
            target_height_m=target_height_m,
            include_terrain=include_terrain,
        )
        if not masks.solar.is_daylight:
            continue
        daylight_samples += 1
        solar_altitudes.append(masks.solar.altitude_deg)
        daylight_dates[when.date()] = _daylight_for_date(dataset, when.date())
        building += masks.building.astype(np.float64) * step
        tree += masks.tree.astype(np.float64) * step
        terrain += masks.terrain.astype(np.float64) * step
        combined += masks.combined.astype(np.float64) * step
        sunlit += (~masks.combined).astype(np.float64) * step
        overlap += (masks.building & masks.tree).astype(np.float64) * step
        if tree_id is not None:
            without = cast_shadows(
                dataset,
                when,
                target_height_m=target_height_m,
                include_terrain=include_terrain,
                exclude_tree_id=tree_id,
            )
            marginal += (masks.combined & ~without.combined).astype(np.float64) * step
        else:
            marginal += (masks.tree & ~masks.building & ~masks.terrain).astype(np.float64) * step
    daylight_sampled = float(daylight_samples) * step
    cells = max(1, grid.width * grid.height)
    mean_daylight = sum(daylight_dates.values()) / len(daylight_dates) if daylight_dates else 0.0
    metrics = {
        "sunlit_fraction": _fraction(sunlit, daylight_sampled, cells),
        "shade_fraction": _fraction(combined, daylight_sampled, cells),
        "building_shade_fraction": _fraction(building, daylight_sampled, cells),
        "tree_shade_fraction": _fraction(tree, daylight_sampled, cells),
        "terrain_shade_fraction": _fraction(terrain, daylight_sampled, cells),
        "overlap_fraction": _fraction(overlap, daylight_sampled, cells),
        "marginal_tree_shade_fraction": _fraction(marginal, daylight_sampled, cells),
        "mean_solar_altitude_deg": float(np.mean(solar_altitudes)) if solar_altitudes else 0.0,
        "mean_daylight_hours": mean_daylight,
        "annual_shade_hours_estimate": (
            _fraction(combined, daylight_sampled, cells) * 365.0 * mean_daylight
        ),
    }
    version = _version(ordered, step, target_height_m, combined, building, tree, marginal)
    return ShadePeriod(
        whens=ordered,
        step_hours=step,
        target_height_m=target_height_m,
        daylight_samples=daylight_samples,
        daylight_sampled_hours=daylight_sampled,
        sunlit_hours=sunlit.astype(np.float32),
        building_shade_hours=building.astype(np.float32),
        tree_shade_hours=tree.astype(np.float32),
        terrain_shade_hours=terrain.astype(np.float32),
        combined_shade_hours=combined.astype(np.float32),
        overlap_hours=overlap.astype(np.float32),
        marginal_tree_shade_hours=marginal.astype(np.float32),
        metrics=metrics,
        image_version=version,
        evidence=SHADE_EVIDENCE,
    )


def shade_at_tree(
    dataset: UrbanForestDataset,
    tree: TreeRecord,
    whens: tuple[dt.datetime, ...],
    *,
    target_height_m: float = 1.5,
    step_hours: float | None = None,
    include_terrain: bool = True,
) -> dict[str, object]:
    """Build the shade card for one tree.

    Parameters
    ----------
    dataset : UrbanForestDataset
        Dataset that contains the tree.
    tree : TreeRecord
        Selected tree.
    whens : tuple of datetime.datetime
        Sample times.
    target_height_m : float
        Height above ground of the target plane.
    step_hours : float or None
        Hours represented by each sample.
    include_terrain : bool
        Include the terrain horizon.

    Returns
    -------
    dict
        Marginal shade, building-shaded fraction, shade efficiency, and evidence.

    Raises
    ------
    ValueError
        When the tree has no projected coordinates.
    """
    if tree.x_m is None or tree.y_m is None:
        raise ValueError("tree has no projected coordinates")
    period = shade_period(
        dataset,
        whens,
        target_height_m=target_height_m,
        step_hours=step_hours,
        include_terrain=include_terrain,
        tree_id=tree.tree_id,
    )
    grid = dataset.terrain
    row, col = _cell_index(grid, tree.x_m, tree.y_m)
    daylight = max(period.daylight_sampled_hours, 1e-9)
    cell_area = _cell_area(grid)
    marginal_area_hours = (
        float(np.sum(period.marginal_tree_shade_hours, dtype=np.float64)) * cell_area
    )
    crown_volume = max(tree_crown_volume_m3(tree), 1e-9)
    total_area = max(grid.width * grid.height * cell_area, 1e-9)
    return {
        "tree_id": tree.tree_id,
        "sun_fraction_at_base": float(period.sunlit_hours[row, col]) / daylight,
        "building_shade_fraction_at_base": float(period.building_shade_hours[row, col]) / daylight,
        "tree_shade_fraction_at_base": float(period.tree_shade_hours[row, col]) / daylight,
        "marginal_shade_area_hours": marginal_area_hours,
        "marginal_shade_fraction": marginal_area_hours / max(total_area * daylight, 1e-9),
        "shade_efficiency_m2h_per_m3": marginal_area_hours / crown_volume,
        "crown_volume_m3": crown_volume,
        "period": period.to_dict(),
        "evidence": SHADE_EVIDENCE.to_dict(),
    }


def shade_png(period: ShadePeriod) -> bytes:
    """Render an aggregated shade period as a transparent PNG.

    Parameters
    ----------
    period : ShadePeriod
        Aggregated period.

    Returns
    -------
    bytes
        PNG bytes.
    """
    rgba = np.zeros((period.height, period.width, 4), dtype=np.uint8)
    building_only = (period.building_shade_hours > 0.0) & (
        period.tree_shade_hours < period.building_shade_hours
    )
    tree_only = (period.tree_shade_hours > 0.0) & (
        period.building_shade_hours < period.tree_shade_hours
    )
    overlap = (period.building_shade_hours > 0.0) & (period.tree_shade_hours > 0.0)
    terrain_only = (period.terrain_shade_hours > 0.0) & ~overlap & ~building_only & ~tree_only
    rgba[building_only] = (43, 94, 170, 145)
    rgba[tree_only] = (45, 125, 72, 150)
    rgba[overlap] = (24, 54, 68, 175)
    rgba[terrain_only] = (90, 90, 90, 95)
    image = Image.fromarray(rgba, mode="RGBA")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def write_shade_product(period: ShadePeriod, out_dir: Path, *, stem: str = "shade") -> Path:
    """Write a JSON summary and PNG overlay for a shade period.

    Parameters
    ----------
    period : ShadePeriod
        Aggregated period.
    out_dir : Path
        Output directory.
    stem : str
        File stem.

    Returns
    -------
    Path
        The JSON path.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = period.to_dict()
    path = out_dir / f"{stem}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (out_dir / f"{stem}.png").write_bytes(shade_png(period))
    np.savez_compressed(
        out_dir / f"{stem}.npz",
        sunlit_hours=period.sunlit_hours,
        building_shade_hours=period.building_shade_hours,
        tree_shade_hours=period.tree_shade_hours,
        terrain_shade_hours=period.terrain_shade_hours,
        combined_shade_hours=period.combined_shade_hours,
        overlap_hours=period.overlap_hours,
        marginal_tree_shade_hours=period.marginal_tree_shade_hours,
    )
    return path


def _fraction(array: NDArray[np.float64], hours: float, cells: int) -> float:
    """Calculate a fraction of cell-hours.

    Parameters
    ----------
    array : numpy.ndarray
        Cell-hour array.
    hours : float
        Daylight sampled hours.
    cells : int
        Number of grid cells.

    Returns
    -------
    float
        Fraction between zero and one.
    """
    if hours <= 0.0 or cells <= 0:
        return 0.0
    return float(np.sum(array, dtype=np.float64) / (hours * cells))


def _cell_area(grid: object) -> float:
    """Calculate cell area from a terrain grid.

    Parameters
    ----------
    grid : object
        Terrain grid.

    Returns
    -------
    float
        Cell area in square metres.
    """
    from fresh_urban_forest.models import TerrainGrid

    if not isinstance(grid, TerrainGrid):
        return 1.0
    return (
        (grid.bounds[2] - grid.bounds[0])
        * (grid.bounds[3] - grid.bounds[1])
        / max(grid.width * grid.height, 1)
    )


def _cell_index(grid: object, x: float, y: float) -> tuple[int, int]:
    """Map projected coordinates to a grid cell.

    Parameters
    ----------
    grid : object
        Terrain grid.
    x : float
        Easting.
    y : float
        Northing.

    Returns
    -------
    tuple of int
        Row and column.
    """
    from fresh_urban_forest.models import TerrainGrid

    if not isinstance(grid, TerrainGrid):
        return (0, 0)
    left, bottom, right, top = grid.bounds
    col = int((x - left) / max(right - left, 1e-9) * grid.width)
    row = int((top - y) / max(top - bottom, 1e-9) * grid.height)
    return (min(max(row, 0), grid.height - 1), min(max(col, 0), grid.width - 1))


def _daylight_for_date(dataset: UrbanForestDataset, date: dt.date) -> float:
    """Calculate daylight hours at the dataset centre.

    Parameters
    ----------
    dataset : UrbanForestDataset
        Dataset that supplies the bounds.
    date : datetime.date
        Calendar date.

    Returns
    -------
    float
        Daylight hours.
    """
    from fresh_urban_forest.terrain import unproject_xy

    left, bottom, right, top = dataset.terrain.bounds
    lon, lat = unproject_xy((left + right) / 2.0, (bottom + top) / 2.0, dataset.terrain.crs)
    return daylight_hours(date, lon, lat)


def _version(
    whens: tuple[dt.datetime, ...],
    step_hours: float,
    target_height_m: float,
    *arrays: NDArray[np.float64],
) -> str:
    """Build a content hash for cache-busting.

    Parameters
    ----------
    whens : tuple of datetime.datetime
        Sample times.
    step_hours : float
        Sample interval.
    target_height_m : float
        Target height.
    arrays : numpy.ndarray
        Raster arrays.

    Returns
    -------
    str
        Short hexadecimal hash.
    """
    digest = hashlib.sha1()
    digest.update("|".join(value.isoformat() for value in whens).encode("utf-8"))
    digest.update(f"|{step_hours}|{target_height_m}".encode())
    for array in arrays:
        digest.update(np.ascontiguousarray(array).tobytes())
    return digest.hexdigest()[:12]
