"""Unified lab report across metrics, shade, birds, completeness, and off-inventory.

The report is a portable JSON bundle. It is not a new model: it composes the existing
evidence-bearing outputs so a scenario can be exported without losing its method caveats.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path

from fresh_urban_forest.completeness import inventory_completeness
from fresh_urban_forest.dataset import dataset_summary
from fresh_urban_forest.demography import project_demography
from fresh_urban_forest.evidence import evidence
from fresh_urban_forest.growth import area_ha
from fresh_urban_forest.habitat import GUILDS, guild_habitat, habitat_metrics
from fresh_urban_forest.metrics import compute_metrics
from fresh_urban_forest.models import CanopyMetrics, TreeRecord, UrbanForestDataset, metrics_to_dict
from fresh_urban_forest.shade import shade_period
from fresh_urban_forest.solar import time_grid

LAB_REPORT_SCHEMA = "fresh-urban-forest.lab-report.v1"


def build_lab_report(
    dataset: UrbanForestDataset,
    *,
    population: Sequence[TreeRecord] | None = None,
    metrics: CanopyMetrics | None = None,
    scenario_id: str | None = None,
    scenario_name: str | None = None,
    year: int = 0,
    off_inventory: Mapping[str, object] | None = None,
    include_shade: bool = True,
    include_birds: bool = True,
) -> dict[str, object]:
    """Compose one scenario report from all evidence-bearing layers.

    Parameters
    ----------
    dataset : UrbanForestDataset
        Base dataset.
    population : sequence of TreeRecord or None
        Scenario population. Defaults to the dataset population.
    metrics : CanopyMetrics or None
        Scenario metrics. Defaults to recomputed tree metrics.
    scenario_id : str or None
        Optional scenario identifier.
    scenario_name : str or None
        Optional scenario name.
    year : int
        Projection year.
    off_inventory : mapping or None
        Optional precomputed off-inventory summary.
    include_shade : bool
        Include a representative-day shade summary.
    include_birds : bool
        Include habitat, guild, and demographic results.

    Returns
    -------
    dict
        Unified, JSON-safe lab report.
    """
    trees = tuple(population) if population is not None else dataset.trees
    report_dataset = replace(dataset, trees=trees)
    hectares = area_ha(dataset.manifest.bounds)
    report_metrics = metrics or compute_metrics(trees, area_ha=hectares)
    summary = dataset_summary(dataset)
    completeness = inventory_completeness(trees)
    report: dict[str, object] = {
        "schema_version": LAB_REPORT_SCHEMA,
        "generated_utc": dt.datetime.now(dt.UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "dataset": summary,
        "scenario": {
            "scenario_id": scenario_id or "",
            "name": scenario_name or "Baseline",
            "year": int(year),
            "is_scenario": scenario_id is not None,
        },
        "metrics": metrics_to_dict(report_metrics),
        "completeness": completeness,
        "off_inventory": _off_inventory_summary(off_inventory),
        "caveats": [
            "Growth and carbon are transparent estimates, not a calibrated local model.",
            "Relative bird abundance is a screening index, not a density.",
            "Bird demography is prior-driven, not a local survival estimate.",
            "Off-inventory candidates are unmatched LiDAR crowns, not confirmed trees.",
            "Shade is a 2.5-D projected surface, not a temperature or cooling measurement.",
        ],
    }
    evidence_items = [
        {
            "layer": "metrics",
            "method": "crown geometry and allometry",
            "tier": "scenario",
        }
    ]
    if include_shade:
        whens = time_grid(dt.date(2026, 6, 21), times=("09:00", "12:00", "15:00", "18:00"))
        period = shade_period(report_dataset, whens, include_terrain=False)
        report["shade"] = period.to_dict()
        evidence_items.append(
            {
                "layer": "shade",
                "method": period.evidence.method,
                "tier": period.evidence.tier,
                "uncertainty": period.evidence.uncertainty,
            }
        )
    if include_birds:
        bird_metrics = habitat_metrics(trees, dataset.terrain)
        guilds = []
        for guild in GUILDS:
            habitat = guild_habitat(bird_metrics, guild)
            demography = project_demography(guild, habitat.suitability, years=25)
            guilds.append({**habitat.to_dict(), "demography": demography.to_dict()})
        report["birds"] = {
            "metrics": bird_metrics.to_dict(),
            "guilds": guilds,
            "caveat": "Relative abundance is a screening index; demography is prior-driven.",
        }
        evidence_items.append(
            {
                "layer": "birds",
                "method": "canopy-structure-habitat-index",
                "tier": "prior",
                "uncertainty": "Guild and demographic coefficients are not locally calibrated.",
            }
        )
    report["evidence"] = evidence_items
    return report


def write_lab_report(report: Mapping[str, object], path: Path) -> Path:
    """Write a unified lab report as JSON.

    Parameters
    ----------
    report : mapping
        Report payload.
    path : Path
        Destination path.

    Returns
    -------
    Path
        The written path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(report), indent=2) + "\n", encoding="utf-8")
    return path


def _off_inventory_summary(payload: Mapping[str, object] | None) -> dict[str, object] | None:
    """Return the public-safe off-inventory summary."""
    if payload is None:
        return None
    return {
        "candidate_count": _as_int(payload.get("candidate_count")),
        "candidate_area_m2": _as_float(payload.get("candidate_area_m2")),
        "detected_count": _as_int(payload.get("detected_count")),
        "matched_count": _as_int(payload.get("matched_count")),
        "land_class": "ownership unknown; candidate-level only",
        "evidence": evidence(
            "physics",
            "lidar-itd-and-inventory-match",
            uncertainty="Unmatched crowns include false positives; no field verification.",
        ).to_dict(),
    }


def _as_int(value: object) -> int:
    """Convert a value to int with a zero default."""
    if isinstance(value, (int, float, str)):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0
    return 0


def _as_float(value: object) -> float:
    """Convert a value to float with a zero default."""
    if isinstance(value, (int, float, str)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    return 0.0
