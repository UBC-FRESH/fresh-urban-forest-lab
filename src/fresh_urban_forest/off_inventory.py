"""Off-inventory urban-tree candidates and value-of-information screening.

The layer is deliberately separate from the official inventory. A detected crown that does
not match an official record is a candidate, not a confirmed tree and not proof of private
ownership. Land class is an inferred proxy unless a real parcel layer is supplied.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

from shapely.geometry import Point, Polygon

from fresh_urban_forest.allometry import (
    estimate_dbh_cm,
    species_group,
)
from fresh_urban_forest.evidence import Evidence, evidence
from fresh_urban_forest.itd import DetectedTree, detect_trees
from fresh_urban_forest.metrics import compute_metrics
from fresh_urban_forest.models import TerrainGrid, TreeRecord, UrbanForestDataset
from fresh_urban_forest.terrain import project_lonlat, sample_terrain_grid
from fresh_urban_forest.validation import validate_detection

if TYPE_CHECKING:
    from fresh_urban_forest.optimize import Solution

OFF_INVENTORY_SCHEMA = "fresh-urban-forest.off-inventory.v1"
OFF_INVENTORY_EVIDENCE = evidence(
    "physics",
    "lidar-itd-and-inventory-match",
    uncertainty=(
        "Unmatched detected crowns include real off-inventory trees, missed inventory "
        "records, and over-segmentation; confidence is a screening score, not a field fact."
    ),
    source="CHM local maxima + marker-controlled watershed, matched to the official inventory",
)


@dataclass(frozen=True, slots=True)
class OffInventoryCandidate:
    """One unmatched detected crown.

    Attributes
    ----------
    candidate_id : str
        Stable candidate identifier.
    detected_id : str
        Underlying detected-crown identifier.
    lon : float
        Longitude.
    lat : float
        Latitude.
    x_m : float
        Projected easting.
    y_m : float
        Projected northing.
    height_m : float
        Detected canopy height.
    crown_radius_m : float
        Equivalent crown radius.
    crown_area_m2 : float
        Segmented crown area.
    nearest_inventory_m : float
        Distance to the nearest official tree.
    land_class : str
        Inferred land class, not legal ownership.
    confidence : float
        Screening confidence from zero to one.
    reasons : tuple of str
        Explanation of the confidence and caveats.
    """

    candidate_id: str
    detected_id: str
    lon: float
    lat: float
    x_m: float
    y_m: float
    height_m: float
    crown_radius_m: float
    crown_area_m2: float
    nearest_inventory_m: float
    land_class: str
    confidence: float
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Convert the candidate to JSON-safe values.

        Returns
        -------
        dict
            Candidate geometry, confidence, and reasons.
        """
        return {
            "candidate_id": self.candidate_id,
            "detected_id": self.detected_id,
            "lon": round(self.lon, 6),
            "lat": round(self.lat, 6),
            "x_m": round(self.x_m, 2),
            "y_m": round(self.y_m, 2),
            "height_m": round(self.height_m, 2),
            "crown_radius_m": round(self.crown_radius_m, 2),
            "crown_area_m2": round(self.crown_area_m2, 1),
            "nearest_inventory_m": round(self.nearest_inventory_m, 2),
            "land_class": self.land_class,
            "confidence": round(self.confidence, 3),
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class OffInventoryReport:
    """Summary of one off-inventory candidate extraction.

    Attributes
    ----------
    schema_version : str
        Result schema.
    dataset_id : str
        Source dataset.
    title : str
        Human-readable title.
    method : str
        Matching and confidence method.
    bbox_wgs84 : tuple of float or None
        Source analysis box.
    detected_count : int
        Detected crowns.
    matched_count : int
        One-to-one matches to official trees.
    unmatched_inventory_count : int
        Official trees without a detected match.
    candidate_count : int
        Filtered off-inventory candidates.
    candidate_area_m2 : float
        Total candidate crown area.
    candidate_canopy_volume_m3 : float
        Total candidate crown volume.
    candidates : tuple of OffInventoryCandidate
        Candidate records.
    evidence : Evidence
        Method and tier.
    """

    schema_version: str
    dataset_id: str
    title: str
    method: str
    bbox_wgs84: tuple[float, float, float, float] | None
    detected_count: int
    matched_count: int
    unmatched_inventory_count: int
    candidate_count: int
    candidate_area_m2: float
    candidate_canopy_volume_m3: float
    candidates: tuple[OffInventoryCandidate, ...]
    evidence: Evidence

    def to_dict(self) -> dict[str, object]:
        """Convert the report to JSON-safe values.

        Returns
        -------
        dict
            Summary and candidate records.
        """
        return {
            "schema_version": self.schema_version,
            "dataset_id": self.dataset_id,
            "title": self.title,
            "method": self.method,
            "bbox_wgs84": list(self.bbox_wgs84) if self.bbox_wgs84 else None,
            "detected_count": self.detected_count,
            "matched_count": self.matched_count,
            "unmatched_inventory_count": self.unmatched_inventory_count,
            "candidate_count": self.candidate_count,
            "candidate_area_m2": round(self.candidate_area_m2, 1),
            "candidate_canopy_volume_m3": round(self.candidate_canopy_volume_m3, 1),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "evidence": self.evidence.to_dict(),
        }

    def to_geojson(self) -> dict[str, object]:
        """Build a public-safe candidate GeoJSON collection.

        Returns
        -------
        dict
            FeatureCollection of candidate points with confidence and land class.
        """
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [candidate.lon, candidate.lat]},
                    "properties": {
                        "candidate_id": candidate.candidate_id,
                        "height_m": round(candidate.height_m, 2),
                        "crown_radius_m": round(candidate.crown_radius_m, 2),
                        "confidence": round(candidate.confidence, 3),
                        "land_class": candidate.land_class,
                        "nearest_inventory_m": round(candidate.nearest_inventory_m, 2),
                    },
                }
                for candidate in self.candidates
            ],
        }


@dataclass(frozen=True, slots=True)
class ValueOfInformation:
    """Comparison of optimization with and without the candidate layer.

    Attributes
    ----------
    official_archive_size : int
        Official-only archive size.
    augmented_archive_size : int
        Augmented archive size.
    official_hypervolume : float
        Official-only hypervolume.
    augmented_hypervolume : float
        Augmented hypervolume.
    official_best_shade : float
        Best shade objective in the official archive.
    augmented_best_shade : float
        Best shade objective in the augmented archive.
    official_best_native : float
        Best native share in the official archive.
    augmented_best_native : float
        Best native share in the augmented archive.
    plan_jaccard : float
        Jaccard overlap of the best-shade planted-site sets.
    changed_sites : int
        Sites whose presence differs between the two plans.
    official_plan_size : int
        Planted sites in the official best-shade plan.
    augmented_plan_size : int
        Planted sites in the augmented best-shade plan.
    candidate_count : int
        Candidates added to the augmented population.
    official_tree_count : int
        Official live-tree count used by the baseline metrics.
    augmented_tree_count : int
        Live-tree count after adding candidates.
    official_canopy_volume_m3 : float
        Official crown-volume total.
    augmented_canopy_volume_m3 : float
        Augmented crown-volume total.
    official_carbon_kg : float
        Official above-ground carbon.
    augmented_carbon_kg : float
        Augmented above-ground carbon.
    evidence : Evidence
        Method and tier.
    """

    official_archive_size: int
    augmented_archive_size: int
    official_hypervolume: float
    augmented_hypervolume: float
    official_best_shade: float
    augmented_best_shade: float
    official_best_native: float
    augmented_best_native: float
    plan_jaccard: float
    changed_sites: int
    official_plan_size: int
    augmented_plan_size: int
    candidate_count: int
    official_tree_count: int
    augmented_tree_count: int
    official_canopy_volume_m3: float
    augmented_canopy_volume_m3: float
    official_carbon_kg: float
    augmented_carbon_kg: float
    evidence: Evidence

    def to_dict(self) -> dict[str, object]:
        """Convert the comparison to JSON-safe values.

        Returns
        -------
        dict
            Archive and plan comparison, evidence, and caveats.
        """
        return {
            "official_archive_size": self.official_archive_size,
            "augmented_archive_size": self.augmented_archive_size,
            "official_hypervolume": round(self.official_hypervolume, 6),
            "augmented_hypervolume": round(self.augmented_hypervolume, 6),
            "official_best_shade": round(self.official_best_shade, 3),
            "augmented_best_shade": round(self.augmented_best_shade, 3),
            "official_best_native": round(self.official_best_native, 4),
            "augmented_best_native": round(self.augmented_best_native, 4),
            "plan_jaccard": round(self.plan_jaccard, 4),
            "changed_sites": self.changed_sites,
            "official_plan_size": self.official_plan_size,
            "augmented_plan_size": self.augmented_plan_size,
            "candidate_count": self.candidate_count,
            "official_tree_count": self.official_tree_count,
            "augmented_tree_count": self.augmented_tree_count,
            "official_canopy_volume_m3": round(self.official_canopy_volume_m3, 3),
            "augmented_canopy_volume_m3": round(self.augmented_canopy_volume_m3, 3),
            "official_carbon_kg": round(self.official_carbon_kg, 3),
            "augmented_carbon_kg": round(self.augmented_carbon_kg, 3),
            "evidence": self.evidence.to_dict(),
            "caveat": (
                "This is a screening comparison. It does not prove that the candidates are "
                "real or private, and it is not a field validation."
            ),
        }


def detect_off_inventory(
    dataset: UrbanForestDataset,
    grid: TerrainGrid,
    *,
    title: str = "Off-inventory candidate layer",
    bbox_wgs84: tuple[float, float, float, float] | None = None,
    min_height_m: float = 3.0,
    window_m: float = 6.0,
    max_distance_m: float = 5.0,
    min_confidence: float = 0.35,
    max_candidates: int = 500,
) -> OffInventoryReport:
    """Detect and classify unmatched crowns against the official inventory.

    Parameters
    ----------
    dataset : UrbanForestDataset
        Dataset with the official inventory.
    grid : TerrainGrid
        Canopy-height grid. Use a high-resolution patch for the pilot.
    title : str
        Human-readable report title.
    bbox_wgs84 : tuple of float or None
        Optional analysis box.
    min_height_m : float
        Minimum detected canopy height.
    window_m : float
        Local-maxima window.
    max_distance_m : float
        Inventory match tolerance.
    min_confidence : float
        Minimum screening confidence.
    max_candidates : int
        Safety cap on candidates.

    Returns
    -------
    OffInventoryReport
        Candidate layer and summary.
    """
    detected = detect_trees(grid, min_height_m=min_height_m, window_m=window_m)
    validation = validate_detection(
        detected,
        dataset.trees,
        max_distance_m=max_distance_m,
        bbox_wgs84=bbox_wgs84,
    )
    detected_by_id = {crown.tree_id: crown for crown in detected}
    boundary = _boundary_polygon(dataset)
    candidates: list[OffInventoryCandidate] = []
    for detected_id in validation.unmatched_detected:
        crown = detected_by_id.get(detected_id)
        if crown is None or crown.height_m < min_height_m:
            continue
        nearest = _nearest_inventory(dataset.trees, crown.x, crown.y)
        confidence = _confidence(crown, nearest)
        if confidence < min_confidence:
            continue
        land_class = _land_class(crown.x, crown.y, boundary)
        reasons = (
            f"height {crown.height_m:.1f} m",
            f"crown radius {crown.crown_radius_m:.1f} m",
            f"{nearest:.1f} m from nearest official tree",
            f"{land_class} (proxy)",
        )
        candidates.append(
            OffInventoryCandidate(
                candidate_id=f"off-{len(candidates) + 1:04d}",
                detected_id=detected_id,
                lon=crown.lon,
                lat=crown.lat,
                x_m=crown.x,
                y_m=crown.y,
                height_m=crown.height_m,
                crown_radius_m=crown.crown_radius_m,
                crown_area_m2=crown.crown_area_m2,
                nearest_inventory_m=nearest,
                land_class=land_class,
                confidence=confidence,
                reasons=reasons,
            )
        )
        if len(candidates) >= max_candidates:
            break
    area = sum(candidate.crown_area_m2 for candidate in candidates)
    volume = sum(
        math.pi / 6.0 * (candidate.crown_radius_m * 2.0) ** 2 * candidate.height_m * 0.5
        for candidate in candidates
    )
    return OffInventoryReport(
        schema_version=OFF_INVENTORY_SCHEMA,
        dataset_id=dataset.manifest.dataset_id,
        title=title,
        method=(
            "CHM local maxima plus marker-controlled watershed; greedy nearest inventory "
            "match; unmatched crowns filtered by height, crown, distance, and confidence."
        ),
        bbox_wgs84=bbox_wgs84,
        detected_count=validation.detected_count,
        matched_count=validation.matched_count,
        unmatched_inventory_count=len(validation.unmatched_inventory),
        candidate_count=len(candidates),
        candidate_area_m2=area,
        candidate_canopy_volume_m3=volume,
        candidates=tuple(candidates),
        evidence=OFF_INVENTORY_EVIDENCE,
    )


def augment_dataset(dataset: UrbanForestDataset, report: OffInventoryReport) -> UrbanForestDataset:
    """Append candidate trees as a separate population.

    Parameters
    ----------
    dataset : UrbanForestDataset
        Official dataset.
    report : OffInventoryReport
        Candidate layer.

    Returns
    -------
    UrbanForestDataset
        Dataset with candidates appended. The official records are untouched.
    """
    extra = tuple(_candidate_tree(candidate, dataset.terrain) for candidate in report.candidates)
    return replace(dataset, trees=dataset.trees + extra)


def value_of_information(
    dataset: UrbanForestDataset,
    report: OffInventoryReport,
    *,
    sites: int = 24,
    horizon: int = 20,
    budget_cad: float = 60_000.0,
    max_sites: int = 40,
    scalarizations: int = 12,
    population: int = 16,
    generations: int = 3,
    local_iterations: int = 100,
    workers: int = 1,
    seed: int = 42,
    center_lonlat: tuple[float, float] | None = None,
    radius_m: float | None = None,
) -> ValueOfInformation:
    """Compare optimization with and without the candidate layer.

    Parameters
    ----------
    dataset : UrbanForestDataset
        Official dataset.
    report : OffInventoryReport
        Candidate layer.
    sites : int
        Candidate planting sites.
    horizon : int
        Projection horizon.
    budget_cad : float
        Budget constraint.
    max_sites : int
        Maximum planted sites.
    scalarizations : int
        Weighted scalarizations.
    population : int
        Solver population.
    generations : int
        Solver generations.
    local_iterations : int
        Local-search iterations.
    workers : int
        Parallel workers.
    seed : int
        Search seed.
    center_lonlat : tuple of float or None
        Optional candidate-site centre.
    radius_m : float or None
        Optional candidate-site radius.

    Returns
    -------
    ValueOfInformation
        Archive and plan comparison.
    """
    from fresh_urban_forest.optimize import build_problem, run_optimization

    official_problem = build_problem(
        dataset,
        site_count=sites,
        horizon=horizon,
        budget_cad=budget_cad,
        max_sites=max_sites,
        seed=seed,
        center_lonlat=center_lonlat,
        radius_m=radius_m,
    )
    augmented_problem = build_problem(
        augment_dataset(dataset, report),
        site_count=sites,
        horizon=horizon,
        budget_cad=budget_cad,
        max_sites=max_sites,
        seed=seed,
        center_lonlat=center_lonlat,
        radius_m=radius_m,
    )
    area_ha = max(
        (dataset.terrain.bounds[2] - dataset.terrain.bounds[0])
        * (dataset.terrain.bounds[3] - dataset.terrain.bounds[1])
        / 10_000.0,
        0.01,
    )
    official_metrics = compute_metrics(dataset.trees, area_ha=area_ha)
    augmented_metrics = compute_metrics(augment_dataset(dataset, report).trees, area_ha=area_ha)
    official = run_optimization(
        official_problem,
        population_size=population,
        generations=generations,
        scalarizations=scalarizations,
        local_iterations=local_iterations,
        workers=workers,
        seed=seed,
    )
    augmented = run_optimization(
        augmented_problem,
        population_size=population,
        generations=generations,
        scalarizations=scalarizations,
        local_iterations=local_iterations,
        workers=workers,
        seed=seed,
    )
    official_best = _best_shade(official.archive.solutions)
    augmented_best = _best_shade(augmented.archive.solutions)
    official_sites = {site for site, _ in official_best.planted}
    augmented_sites = {site for site, _ in augmented_best.planted}
    union = official_sites | augmented_sites
    jaccard = len(official_sites & augmented_sites) / len(union) if union else 1.0
    return ValueOfInformation(
        official_archive_size=len(official.archive.solutions),
        augmented_archive_size=len(augmented.archive.solutions),
        official_hypervolume=official.archive.hypervolume,
        augmented_hypervolume=augmented.archive.hypervolume,
        official_best_shade=official_best.metrics.get("shade_m2h", 0.0),
        augmented_best_shade=augmented_best.metrics.get("shade_m2h", 0.0),
        official_best_native=max(
            (
                solution.metrics.get("native_fraction", 0.0)
                for solution in official.archive.solutions
            ),
            default=0.0,
        ),
        augmented_best_native=max(
            (
                solution.metrics.get("native_fraction", 0.0)
                for solution in augmented.archive.solutions
            ),
            default=0.0,
        ),
        plan_jaccard=jaccard,
        changed_sites=len(official_sites.symmetric_difference(augmented_sites)),
        official_plan_size=len(official_sites),
        augmented_plan_size=len(augmented_sites),
        candidate_count=report.candidate_count,
        official_tree_count=official_metrics.tree_count,
        augmented_tree_count=augmented_metrics.tree_count,
        official_canopy_volume_m3=official_metrics.canopy_volume_m3,
        augmented_canopy_volume_m3=augmented_metrics.canopy_volume_m3,
        official_carbon_kg=official_metrics.total_carbon_kg,
        augmented_carbon_kg=augmented_metrics.total_carbon_kg,
        evidence=evidence(
            "scenario",
            "p8-value-of-information",
            uncertainty=(
                "The comparison uses a screening candidate layer, a finite Pareto archive, "
                "and a fixed solver budget; it is not a field-validated decision."
            ),
            source="P8 optimizer on official and augmented populations",
        ),
    )


def write_report(report: OffInventoryReport, out_dir: Path) -> Path:
    """Write the JSON and public GeoJSON candidate layer.

    Parameters
    ----------
    report : OffInventoryReport
        Candidate report.
    out_dir : Path
        Destination directory.

    Returns
    -------
    Path
        The JSON path.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "off_inventory.json"
    path.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    (out_dir / "off_inventory.geojson").write_text(
        json.dumps(report.to_geojson(), indent=1) + "\n",
        encoding="utf-8",
    )
    return path


def write_value_of_information(value: ValueOfInformation, path: Path) -> Path:
    """Write a value-of-information comparison.

    Parameters
    ----------
    value : ValueOfInformation
        Comparison.
    path : Path
        Destination JSON.

    Returns
    -------
    Path
        The written path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path


def _candidate_tree(candidate: OffInventoryCandidate, grid: TerrainGrid) -> TreeRecord:
    """Convert a candidate to a separate tree record."""
    group = species_group("Unknown off-inventory")
    dbh = estimate_dbh_cm(candidate.height_m, group)
    elevation, _, _ = _sample_height(grid, candidate.lon, candidate.lat)
    return TreeRecord(
        tree_id=f"off:{candidate.candidate_id}",
        lon=candidate.lon,
        lat=candidate.lat,
        species="Unknown off-inventory",
        common_name="Off-inventory candidate",
        genus="",
        dbh_cm=round(dbh, 2),
        height_m=round(candidate.height_m, 2),
        crown_width_m=round(candidate.crown_radius_m * 2.0, 2),
        crown_ratio=0.5,
        status="alive",
        source="off_inventory",
        source_date="2021",
        native=None,
        x_m=candidate.x_m,
        y_m=candidate.y_m,
        elevation_m=round(elevation, 2),
        lidar_height_m=round(candidate.height_m, 2),
        attributes={
            "off_inventory_confidence": str(candidate.confidence),
            "land_class": candidate.land_class,
            "candidate_id": candidate.candidate_id,
        },
    )


def _sample_height(grid: TerrainGrid, lon: float, lat: float) -> tuple[float, float, float]:
    """Sample elevation and canopy at a candidate."""
    return sample_terrain_grid(grid, lon, lat)


def _nearest_inventory(
    trees: tuple[TreeRecord, ...] | list[TreeRecord], x: float, y: float
) -> float:
    """Return distance to the nearest official tree."""
    distances = [
        math.hypot(tree.x_m - x, tree.y_m - y)
        for tree in trees
        if tree.x_m is not None and tree.y_m is not None
    ]
    return min(distances) if distances else 1_000.0


def _confidence(crown: DetectedTree, nearest: float) -> float:
    """Score a candidate from height, crown size, and isolation."""
    height_score = min(crown.height_m / 25.0, 1.0)
    crown_score = min(crown.crown_radius_m / 8.0, 1.0)
    isolation = min(nearest / 20.0, 1.0)
    return round(0.4 * height_score + 0.3 * crown_score + 0.3 * isolation, 3)


def _land_class(x: float, y: float, boundary: Polygon | None) -> str:
    """Return an inferred land class, not legal ownership."""
    if boundary is None:
        return "inside analysis area (ownership unknown)"
    return (
        "inside analysis boundary (ownership unknown)"
        if boundary.contains(Point(x, y))
        else "outside analysis boundary (ownership unknown)"
    )


def _boundary_polygon(dataset: UrbanForestDataset) -> Polygon | None:
    """Project the dataset boundary for the land-class proxy."""
    if not dataset.boundary:
        return None
    points = [project_lonlat(lon, lat, dataset.terrain.crs) for lon, lat in dataset.boundary]
    if len(points) < 3:
        return None
    polygon = Polygon(points)
    return polygon if polygon.is_valid else polygon.buffer(0)


def _best_shade(solutions: tuple[Solution, ...]) -> Solution:
    """Return the solution with the largest shade metric."""
    if not solutions:
        raise ValueError("archive has no solutions")
    return max(
        solutions,
        key=lambda solution: float(solution.metrics.get("shade_m2h", 0.0)),
    )
