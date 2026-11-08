"""Site-level scenario shade evaluation.

The evaluator adds hypothetical trees from a validated site scenario to a dataset and
runs the existing projected-shadow accumulation model on the same time samples and target
height as the baseline. It reports method labels, per-site deltas, and optional
height/crown sensitivity. It is a scenario screen, not an observed outcome.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

import numpy as np

from fresh_urban_forest.evidence import Evidence, evidence
from fresh_urban_forest.models import TerrainGrid, TreeRecord, UrbanForestDataset
from fresh_urban_forest.shade import SHADE_EVIDENCE, ShadePeriod, shade_period
from fresh_urban_forest.site_scenario import CandidateSite, ScenarioSite, SiteScenario
from fresh_urban_forest.terrain import project_lonlat

SITE_SHADE_EVIDENCE = evidence(
    "physics",
    "p48-site-scenario-shadow-evaluation",
    uncertainty=(
        "Hypothetical tree crowns are evaluated with the same 2.5-D shadow model as the "
        "baseline. The result is a scenario screen, not observed shade, survival, cooling, "
        "or field validation; P45's unresolved citywide change direction remains in force."
    ),
    source="Existing projected-shadow accumulation plus explicit scenario tree assumptions.",
)


@dataclass(frozen=True, slots=True)
class SiteContribution:
    """Shade contribution from one scenario site.

    Attributes
    ----------
    site_id : str
        Candidate site identifier.
    trees : int
        Number of hypothetical trees at the site.
    baseline_shade_m2h : float
        Baseline combined shade area-hours.
    scenario_shade_m2h : float
        Baseline plus this site.
    delta_shade_m2h : float
        Additional shade area-hours.
    delta_shade_pct : float or None
        Percent change from baseline, or ``None`` when baseline is zero.
    """

    site_id: str
    trees: int
    baseline_shade_m2h: float
    scenario_shade_m2h: float
    delta_shade_m2h: float
    delta_shade_pct: float | None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe contribution record.

        Returns
        -------
        dict
            Site contribution fields.
        """
        return {
            "site_id": self.site_id,
            "trees": self.trees,
            "baseline_shade_m2h": round(self.baseline_shade_m2h, 2),
            "scenario_shade_m2h": round(self.scenario_shade_m2h, 2),
            "delta_shade_m2h": round(self.delta_shade_m2h, 2),
            "delta_shade_pct": (
                round(self.delta_shade_pct, 4) if self.delta_shade_pct is not None else None
            ),
        }


@dataclass(frozen=True, slots=True)
class ShadeSensitivity:
    """One height or crown sensitivity case.

    Attributes
    ----------
    case : str
        Sensitivity case label.
    height_scale : float
        Height multiplier.
    crown_scale : float
        Crown-width multiplier.
    scenario_shade_m2h : float
        Scenario shade area-hours.
    delta_shade_m2h : float
        Additional shade area-hours versus baseline.
    delta_shade_pct : float or None
        Percent change from baseline, or ``None`` when baseline is zero.
    """

    case: str
    height_scale: float
    crown_scale: float
    scenario_shade_m2h: float
    delta_shade_m2h: float
    delta_shade_pct: float | None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe sensitivity case.

        Returns
        -------
        dict
            Sensitivity fields.
        """
        return {
            "case": self.case,
            "height_scale": self.height_scale,
            "crown_scale": self.crown_scale,
            "scenario_shade_m2h": round(self.scenario_shade_m2h, 2),
            "delta_shade_m2h": round(self.delta_shade_m2h, 2),
            "delta_shade_pct": (
                round(self.delta_shade_pct, 4) if self.delta_shade_pct is not None else None
            ),
        }


@dataclass(frozen=True, slots=True)
class SiteScenarioEvaluation:
    """Baseline-versus-scenario shade evaluation.

    Attributes
    ----------
    scenario_id : str
        Scenario identifier.
    label : str
        Scenario label.
    method : str
        Shade method label.
    baseline_shade_m2h : float
        Baseline combined shade area-hours.
    scenario_shade_m2h : float
        Scenario combined shade area-hours.
    delta_shade_m2h : float
        Additional shade area-hours.
    delta_shade_pct : float or None
        Percent change from baseline, or ``None`` when baseline is zero.
    baseline_shade_fraction : float
        Baseline combined shade fraction.
    scenario_shade_fraction : float
        Scenario combined shade fraction.
    per_site : tuple of SiteContribution
        Per-site contributions, empty when not requested.
    sensitivity : tuple of ShadeSensitivity
        Height/crown sensitivity cases, empty when not requested.
    settings : mapping
        Shared evaluation settings.
    uncertainty : mapping
        Method labels and caveats.
    evidence : Evidence
        Method and evidence tier.
    """

    scenario_id: str
    label: str
    method: str
    baseline_shade_m2h: float
    scenario_shade_m2h: float
    delta_shade_m2h: float
    delta_shade_pct: float | None
    baseline_shade_fraction: float
    scenario_shade_fraction: float
    per_site: tuple[SiteContribution, ...]
    sensitivity: tuple[ShadeSensitivity, ...]
    settings: Mapping[str, object]
    uncertainty: Mapping[str, object]
    evidence: Evidence

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe evaluation document.

        Returns
        -------
        dict
            Evaluation metrics, per-site records, sensitivity, settings, and caveats.
        """
        return {
            "scenario_id": self.scenario_id,
            "label": self.label,
            "method": self.method,
            "baseline_shade_m2h": round(self.baseline_shade_m2h, 2),
            "scenario_shade_m2h": round(self.scenario_shade_m2h, 2),
            "delta_shade_m2h": round(self.delta_shade_m2h, 2),
            "delta_shade_pct": (
                round(self.delta_shade_pct, 4) if self.delta_shade_pct is not None else None
            ),
            "baseline_shade_fraction": round(self.baseline_shade_fraction, 6),
            "scenario_shade_fraction": round(self.scenario_shade_fraction, 6),
            "per_site": [site.to_dict() for site in self.per_site],
            "sensitivity": [case.to_dict() for case in self.sensitivity],
            "settings": dict(self.settings),
            "uncertainty": dict(self.uncertainty),
            "evidence": self.evidence.to_dict(),
        }


def evaluate_site_scenario(
    dataset: UrbanForestDataset,
    scenario: SiteScenario,
    candidates: Mapping[str, CandidateSite],
    whens: Sequence[dt.datetime],
    *,
    target_height_m: float = 1.5,
    step_hours: float | None = None,
    include_terrain: bool = False,
    include_per_site: bool = True,
    include_sensitivity: bool = False,
) -> SiteScenarioEvaluation:
    """Evaluate baseline and scenario shade for explicit site placements.

    Parameters
    ----------
    dataset : UrbanForestDataset
        Baseline dataset.
    scenario : SiteScenario
        Validated scenario.
    candidates : mapping
        Candidate sites keyed by site id.
    whens : sequence of datetime.datetime
        Evaluation samples.
    target_height_m : float
        Target plane height above ground.
    step_hours : float or None
        Hours represented by each sample; inferred when omitted.
    include_terrain : bool
        Include the coarse terrain horizon.
    include_per_site : bool
        Evaluate each site separately against baseline.
    include_sensitivity : bool
        Evaluate height and crown-width sensitivity cases.

    Returns
    -------
    SiteScenarioEvaluation
        Baseline, scenario, per-site, and sensitivity metrics.

    Raises
    ------
    ValueError
        When the time samples are empty or a scenario site has no candidate.
    """
    ordered = tuple(sorted(whens))
    if not ordered:
        raise ValueError("whens must contain at least one sample")
    if target_height_m <= 0.0:
        raise ValueError("target_height_m must be positive")
    baseline = shade_period(
        dataset,
        ordered,
        target_height_m=target_height_m,
        step_hours=step_hours,
        include_terrain=include_terrain,
    )
    scenario_trees = _scenario_trees(dataset, scenario, candidates)
    scenario_dataset = replace(dataset, trees=dataset.trees + scenario_trees)
    scenario_period = shade_period(
        scenario_dataset,
        ordered,
        target_height_m=target_height_m,
        step_hours=step_hours,
        include_terrain=include_terrain,
    )
    cell_area_m2 = _terrain_cell_area(dataset.terrain)
    baseline_area_hours = _shade_area_hours(baseline, cell_area_m2)
    scenario_area_hours = _shade_area_hours(scenario_period, cell_area_m2)
    delta_area_hours = scenario_area_hours - baseline_area_hours
    delta_pct = _percent_delta(delta_area_hours, baseline_area_hours)
    per_site: list[SiteContribution] = []
    if include_per_site:
        for site in scenario.sites:
            tree_records = _site_trees(dataset, scenario.scenario_id, site, candidates)
            site_dataset = replace(dataset, trees=dataset.trees + tree_records)
            site_period = shade_period(
                site_dataset,
                ordered,
                target_height_m=target_height_m,
                step_hours=step_hours,
                include_terrain=include_terrain,
            )
            site_hours = _shade_area_hours(site_period, cell_area_m2)
            site_delta = site_hours - baseline_area_hours
            per_site.append(
                SiteContribution(
                    site_id=site.site_id,
                    trees=site.count,
                    baseline_shade_m2h=baseline_area_hours,
                    scenario_shade_m2h=site_hours,
                    delta_shade_m2h=site_delta,
                    delta_shade_pct=_percent_delta(site_delta, baseline_area_hours),
                )
            )
    sensitivity: list[ShadeSensitivity] = []
    if include_sensitivity:
        for case, height_scale, crown_scale in (
            ("height_minus_20pct", 0.8, 1.0),
            ("height_plus_20pct", 1.2, 1.0),
            ("crown_minus_20pct", 1.0, 0.8),
            ("crown_plus_20pct", 1.0, 1.2),
        ):
            scaled_trees = _scenario_trees(
                dataset,
                scenario,
                candidates,
                height_scale=height_scale,
                crown_scale=crown_scale,
            )
            scaled_dataset = replace(dataset, trees=dataset.trees + scaled_trees)
            scaled_period = shade_period(
                scaled_dataset,
                ordered,
                target_height_m=target_height_m,
                step_hours=step_hours,
                include_terrain=include_terrain,
            )
            scaled_hours = _shade_area_hours(scaled_period, cell_area_m2)
            scaled_delta = scaled_hours - baseline_area_hours
            sensitivity.append(
                ShadeSensitivity(
                    case=case,
                    height_scale=height_scale,
                    crown_scale=crown_scale,
                    scenario_shade_m2h=scaled_hours,
                    delta_shade_m2h=scaled_delta,
                    delta_shade_pct=_percent_delta(scaled_delta, baseline_area_hours),
                )
            )
    settings: dict[str, object] = {
        "target_height_m": target_height_m,
        "step_hours": scenario_period.step_hours,
        "include_terrain": include_terrain,
        "whens": [value.isoformat() for value in ordered],
        "site_count": len(scenario.sites),
        "tree_count": sum(site.count for site in scenario.sites),
    }
    uncertainty: dict[str, object] = {
        "model": "projected-shadow-accumulation",
        "status": "scenario screen, not observed shade",
        "p45_citywide_change": "unresolved; do not infer a citywide net direction",
        "shade_evidence": SHADE_EVIDENCE.to_dict(),
        "caveats": [
            "Hypothetical species, height, and crown assumptions are user-declared.",
            "The scenario is not a planting plan, survival estimate, or field validation.",
            "Cost, water, and maintenance are not biophysical shade outputs.",
        ],
    }
    return SiteScenarioEvaluation(
        scenario_id=scenario.scenario_id,
        label=scenario.label,
        method="projected-shadow-accumulation-combined",
        baseline_shade_m2h=baseline_area_hours,
        scenario_shade_m2h=scenario_area_hours,
        delta_shade_m2h=delta_area_hours,
        delta_shade_pct=delta_pct,
        baseline_shade_fraction=float(baseline.metrics["shade_fraction"]),
        scenario_shade_fraction=float(scenario_period.metrics["shade_fraction"]),
        per_site=tuple(per_site),
        sensitivity=tuple(sensitivity),
        settings=settings,
        uncertainty=uncertainty,
        evidence=SITE_SHADE_EVIDENCE,
    )


def _scenario_trees(
    dataset: UrbanForestDataset,
    scenario: SiteScenario,
    candidates: Mapping[str, CandidateSite],
    *,
    height_scale: float = 1.0,
    crown_scale: float = 1.0,
) -> tuple[TreeRecord, ...]:
    """Build hypothetical tree records for a scenario."""
    trees: list[TreeRecord] = []
    for site in scenario.sites:
        trees.extend(
            _site_trees(
                dataset,
                scenario.scenario_id,
                site,
                candidates,
                height_scale=height_scale,
                crown_scale=crown_scale,
            )
        )
    return tuple(trees)


def _site_trees(
    dataset: UrbanForestDataset,
    scenario_id: str,
    site: ScenarioSite,
    candidates: Mapping[str, CandidateSite],
    *,
    height_scale: float = 1.0,
    crown_scale: float = 1.0,
) -> tuple[TreeRecord, ...]:
    """Build hypothetical tree records for one site."""
    candidate = candidates.get(site.site_id)
    if candidate is None:
        raise ValueError(f"scenario site has no candidate: {site.site_id}")
    x, y = project_lonlat(candidate.lon, candidate.lat, dataset.terrain.crs)
    elevation = _sample_elevation(dataset.terrain, x, y)
    height = max(site.height_m * height_scale, 0.5)
    crown_width = max(site.crown_radius_m * 2.0 * crown_scale, 0.5)
    return tuple(
        TreeRecord(
            tree_id=f"scenario:{scenario_id}:{site.site_id}:{index}",
            lon=candidate.lon,
            lat=candidate.lat,
            species=site.species,
            common_name=site.species,
            height_m=height,
            crown_width_m=crown_width,
            crown_ratio=0.5,
            status="planted",
            source="site-scenario",
            x_m=x,
            y_m=y,
            elevation_m=elevation,
        )
        for index in range(site.count)
    )


def _sample_elevation(grid: TerrainGrid, x: float, y: float) -> float:
    """Sample the terrain elevation at a projected point."""
    left, bottom, right, top = grid.bounds
    col = int((x - left) / max(right - left, 1e-9) * grid.width)
    row = int((top - y) / max(top - bottom, 1e-9) * grid.height)
    row = min(max(row, 0), grid.height - 1)
    col = min(max(col, 0), grid.width - 1)
    return float(np.nan_to_num(grid.elevation[row, col], nan=0.0))


def _terrain_cell_area(grid: TerrainGrid) -> float:
    """Return terrain cell area in square metres."""
    return (
        (grid.bounds[2] - grid.bounds[0])
        * (grid.bounds[3] - grid.bounds[1])
        / max(grid.width * grid.height, 1)
    )


def _shade_area_hours(period: ShadePeriod, cell_area_m2: float) -> float:
    """Return combined shade area-hours from a period."""
    return float(np.sum(period.combined_shade_hours, dtype=np.float64)) * cell_area_m2


def _percent_delta(delta: float, baseline: float) -> float | None:
    """Return percent change, or ``None`` for a zero baseline."""
    if abs(baseline) <= 1e-12:
        return None
    return delta / baseline * 100.0


__all__ = [
    "SITE_SHADE_EVIDENCE",
    "ShadeSensitivity",
    "SiteContribution",
    "SiteScenarioEvaluation",
    "evaluate_site_scenario",
]
