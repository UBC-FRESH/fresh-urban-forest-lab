"""Candidate planting sites and explicit site-level scenario contracts.

The candidate layer is an above-ground screen derived from P39 canopy-gap masks.
A scenario is a hypothetical set of tree placements with explicit assumptions. Neither
object is a planting plan, an ownership record, or a field-validated recommendation.
"""

from __future__ import annotations

import json
import math
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import numpy as np
from pyproj import Transformer
from scipy.ndimage import label

from fresh_urban_forest.evidence import evidence
from fresh_urban_forest.planting_opportunity import GapMasks

SITE_CANDIDATES_SCHEMA_VERSION = "fresh-urban-forest.site-candidates.v1"
SITE_SCENARIO_SCHEMA_VERSION = "fresh-urban-forest.site-scenario.v1"
DEFAULT_SITE_MIN_AREA_M2 = 45.0
DEFAULT_MAX_CANDIDATE_SITES = 5_000
DEFAULT_MAX_SITES_PER_CELL = 12
DEFAULT_MAX_SCENARIO_SITES = 200
DEFAULT_MAX_TREES = 1_000
DEFAULT_CELL_SIZE_M = 400.0

CANDIDATE_EVIDENCE = evidence(
    "scenario",
    "p39-gap-component-candidate",
    uncertainty=(
        "A candidate site is a contiguous open-ground component from a LiDAR gap screen. "
        "It is not a parcel, a planting permit, a utility clearance, or evidence of access."
    ),
    source="P39 canopy-gap masks; P42/P44 action labels are joined as context only.",
)

SITE_SCENARIO_EVIDENCE = evidence(
    "scenario",
    "explicit-site-scenario",
    uncertainty=(
        "A site scenario is a hypothetical placement with user-declared species, size, "
        "cost, water, and maintenance assumptions. Shade and benefit numbers are not "
        "observed outcomes, survival estimates, or field validation."
    ),
    source="P39/P42 candidate context plus explicit scenario inputs.",
)

_ACTION_RANK = {
    "plant_cool": 0,
    "expand_canopy": 1,
    "structural_shade": 2,
    "protect_loss": 3,
    "monitor": 4,
    "unassigned": 5,
}


@dataclass(frozen=True, slots=True)
class CandidateSite:
    """One deterministic candidate planting site.

    Attributes
    ----------
    site_id : str
        Stable identifier derived from the 400 m cell and component rank.
    cell_id : str
        Global 400 m cell identifier.
    lon : float
        WGS84 longitude of the component centroid.
    lat : float
        WGS84 latitude of the component centroid.
    area_m2 : float
        Component area in square metres.
    street_adjacent : bool
        Whether the component intersects the P39 street-adjacent gap.
    action_class : str
        Joined P42/P44 action code, or ``unassigned``.
    action_label : str
        Human-readable action label.
    opportunity_tier : str
        Joined P39 opportunity tier, or ``unknown``.
    source : str
        Candidate source label.
    evidence_tier : str
        Evidence tier for the candidate screen.
    """

    site_id: str
    cell_id: str
    lon: float
    lat: float
    area_m2: float
    street_adjacent: bool
    action_class: str
    action_label: str
    opportunity_tier: str
    source: str = "p39_edge_gap"
    evidence_tier: str = "candidate"

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe candidate record.

        Returns
        -------
        dict
            Candidate fields without ownership or address data.
        """
        return {
            "site_id": self.site_id,
            "cell_id": self.cell_id,
            "lon": round(self.lon, 6),
            "lat": round(self.lat, 6),
            "area_m2": round(self.area_m2, 1),
            "street_adjacent": self.street_adjacent,
            "action_class": self.action_class,
            "action_label": self.action_label,
            "opportunity_tier": self.opportunity_tier,
            "source": self.source,
            "evidence_tier": self.evidence_tier,
        }

    def to_feature(self) -> dict[str, object]:
        """Return a GeoJSON point feature for the candidate.

        Returns
        -------
        dict
            GeoJSON feature with candidate properties.
        """
        return {
            "type": "Feature",
            "properties": self.to_dict(),
            "geometry": {"type": "Point", "coordinates": [round(self.lon, 6), round(self.lat, 6)]},
        }


@dataclass(frozen=True, slots=True)
class ScenarioSite:
    """One hypothetical tree placement in a site scenario.

    Attributes
    ----------
    site_id : str
        Candidate site identifier.
    species : str
        User-declared species label.
    height_m : float
        Declared planting height in metres.
    crown_radius_m : float
        Declared crown radius in metres.
    count : int
        Number of trees at the site.
    cost_cad : float
        Declared cost in Canadian dollars.
    water_l_per_year : float
        Declared irrigation water in litres per year.
    maintenance : str
        Declared maintenance assumption.
    assumption_source : str
        Where the assumption came from.
    """

    site_id: str
    species: str
    height_m: float
    crown_radius_m: float
    count: int
    cost_cad: float
    water_l_per_year: float
    maintenance: str
    assumption_source: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe scenario-site record.

        Returns
        -------
        dict
            Scenario site fields.
        """
        return {
            "site_id": self.site_id,
            "species": self.species,
            "height_m": round(self.height_m, 2),
            "crown_radius_m": round(self.crown_radius_m, 2),
            "count": self.count,
            "cost_cad": round(self.cost_cad, 2),
            "water_l_per_year": round(self.water_l_per_year, 2),
            "maintenance": self.maintenance,
            "assumption_source": self.assumption_source,
        }


@dataclass(frozen=True, slots=True)
class SiteScenario:
    """A validated, explicit site-level scenario.

    Attributes
    ----------
    scenario_id : str
        Stable scenario identifier.
    label : str
        Human-readable scenario label.
    created_at : str
        ISO timestamp.
    sites : tuple of ScenarioSite
        Hypothetical placements.
    settings : mapping
        Time, model, and other shared evaluation settings.
    totals : mapping
        Derived site, tree, cost, and water totals.
    metrics : mapping
        Optional evaluated metrics, empty before P48.2.
    uncertainty : mapping
        Method labels, sensitivity, and caveats.
    """

    scenario_id: str
    label: str
    created_at: str
    sites: tuple[ScenarioSite, ...]
    settings: Mapping[str, object] = field(default_factory=dict)
    totals: Mapping[str, float | int] = field(default_factory=dict)
    metrics: Mapping[str, float | int | None] = field(default_factory=dict)
    uncertainty: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe scenario document.

        Returns
        -------
        dict
            Scenario fields with the current schema version.
        """
        return {
            "schema_version": SITE_SCENARIO_SCHEMA_VERSION,
            "scenario_id": self.scenario_id,
            "label": self.label,
            "created_at": self.created_at,
            "settings": dict(self.settings),
            "sites": [site.to_dict() for site in self.sites],
            "totals": dict(self.totals),
            "metrics": dict(self.metrics),
            "uncertainty": dict(self.uncertainty),
        }


def extract_candidate_sites(
    masks: GapMasks,
    *,
    bounds: tuple[float, float, float, float],
    crs: str,
    action_cells: Mapping[str, Mapping[str, object]] | None = None,
    site_min_area_m2: float = DEFAULT_SITE_MIN_AREA_M2,
    cell_size_m: float = DEFAULT_CELL_SIZE_M,
    max_sites: int = DEFAULT_MAX_CANDIDATE_SITES,
    max_sites_per_cell: int = DEFAULT_MAX_SITES_PER_CELL,
) -> tuple[CandidateSite, ...]:
    """Extract deterministic candidate sites from contiguous gap components.

    Parameters
    ----------
    masks : GapMasks
        P39 gap masks.
    bounds : tuple of float
        ``(left, bottom, right, top)`` in the projected CRS.
    crs : str
        Projected CRS.
    action_cells : mapping or None
        P42/P44 cells keyed by cell id for context labels.
    site_min_area_m2 : float
        Minimum component area.
    cell_size_m : float
        Analysis cell size.
    max_sites : int
        Global candidate cap.
    max_sites_per_cell : int
        Per-cell candidate cap.

    Returns
    -------
    tuple of CandidateSite
        Deterministic candidate sites, ordered by action rank, area, cell, and id.

    Raises
    ------
    ValueError
        When a threshold is non-positive or the gap mask shape is empty.
    """
    if site_min_area_m2 <= 0.0:
        raise ValueError("site_min_area_m2 must be positive")
    if cell_size_m <= 0.0:
        raise ValueError("cell_size_m must be positive")
    if max_sites <= 0 or max_sites_per_cell <= 0:
        raise ValueError("site caps must be positive")
    gap = np.asarray(masks.gap, dtype=np.bool_)
    if gap.ndim != 2 or gap.size == 0:
        raise ValueError("gap mask must be a non-empty two-dimensional array")
    height, width = gap.shape
    left, bottom, right, top = bounds
    if right <= left or top <= bottom:
        raise ValueError("bounds must be positive")
    pixel_x = (right - left) / width
    pixel_y = (top - bottom) / height
    pixel_area = pixel_x * pixel_y
    components, count = label(gap, structure=np.ones((3, 3)))
    if count == 0:
        return ()
    flat = components.ravel()
    weights = np.bincount(flat, minlength=count + 1).astype(np.float64)
    columns = np.tile(np.arange(width, dtype=np.float64), height)
    rows = np.repeat(np.arange(height, dtype=np.float64), width)
    sum_x = np.bincount(flat, weights=columns, minlength=count + 1)
    sum_y = np.bincount(flat, weights=rows, minlength=count + 1)
    street_counts = np.bincount(
        flat,
        weights=np.asarray(masks.street_gap, dtype=np.float64).ravel(),
        minlength=count + 1,
    )
    transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    records: list[tuple[float, str, float, float, int, bool]] = []
    for index in range(1, count + 1):
        component_area = weights[index] * pixel_area
        if weights[index] <= 0 or component_area < site_min_area_m2:
            continue
        column = sum_x[index] / weights[index]
        row = sum_y[index] / weights[index]
        x = left + (column + 0.5) * pixel_x
        y = top - (row + 0.5) * pixel_y
        cell_x = math.floor((x - left) / cell_size_m)
        cell_y = math.floor((top - y) / cell_size_m)
        cell_id = f"r{cell_y:02d}c{cell_x:02d}"
        records.append((component_area, cell_id, x, y, index, street_counts[index] > 0.0))
    if not records:
        return ()

    by_cell: dict[str, list[tuple[float, str, float, float, int, bool]]] = {}
    for record in records:
        by_cell.setdefault(record[1], []).append(record)
    ranked: list[tuple[float, str, float, float, int, bool, str]] = []
    for cell_id, cell_records in by_cell.items():
        ordered = sorted(cell_records, key=lambda item: (-item[0], item[3], item[2]))
        for rank, record in enumerate(ordered[:max_sites_per_cell], start=1):
            ranked.append((*record, f"gap-{cell_id}-{rank:04d}"))

    def _rank(item: tuple[float, str, float, float, int, bool, str]) -> tuple[object, ...]:
        action = _action_for_cell(item[1], action_cells)
        action_class = str(action.get("action_class", "unassigned"))
        return (_ACTION_RANK.get(action_class, 5), -item[0], item[1], item[6])

    ranked.sort(key=_rank)
    selected = ranked[:max_sites]
    sites: list[CandidateSite] = []
    for area, cell_id, x, y, _index, street, site_id in selected:
        lon, lat = transformer.transform(x, y)
        action = _action_for_cell(cell_id, action_cells)
        action_class = str(action.get("action_class", "unassigned"))
        action_label = str(action.get("action_label", "unassigned"))
        tier = str(action.get("opportunity_tier", "unknown"))
        sites.append(
            CandidateSite(
                site_id=site_id,
                cell_id=cell_id,
                lon=float(lon),
                lat=float(lat),
                area_m2=float(area),
                street_adjacent=bool(street),
                action_class=action_class,
                action_label=action_label,
                opportunity_tier=tier,
            )
        )
    return tuple(sites)


def _action_for_cell(
    cell_id: str,
    action_cells: Mapping[str, Mapping[str, object]] | None,
) -> Mapping[str, object]:
    """Return the action context for one cell, or an empty mapping."""
    if action_cells is None:
        return {}
    return action_cells.get(cell_id, {})


def candidate_sites_document(
    sites: Sequence[CandidateSite],
    *,
    metadata: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build the versioned candidate-site document.

    Parameters
    ----------
    sites : sequence of CandidateSite
        Candidate sites.
    metadata : mapping or None
        Build metadata and caveats.

    Returns
    -------
    dict
        JSON-safe candidate document.
    """
    return {
        "schema_version": SITE_CANDIDATES_SCHEMA_VERSION,
        "metadata": dict(metadata or {}),
        "sites": [site.to_dict() for site in sites],
    }


def candidate_sites_geojson(
    sites: Sequence[CandidateSite],
    *,
    metadata: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build a WGS84 GeoJSON candidate collection.

    Parameters
    ----------
    sites : sequence of CandidateSite
        Candidate sites.
    metadata : mapping or None
        Build metadata.

    Returns
    -------
    dict
        GeoJSON FeatureCollection.
    """
    return {
        "type": "FeatureCollection",
        "name": "site_candidates",
        "metadata": dict(metadata or {}),
        "features": [site.to_feature() for site in sites],
    }


def write_candidate_site_product(
    sites: Sequence[CandidateSite],
    out_dir: Path,
    *,
    metadata: Mapping[str, object] | None = None,
    stem: str = "site_candidates",
) -> dict[str, Path]:
    """Write candidate JSON, GeoJSON, and metadata files.

    Parameters
    ----------
    sites : sequence of CandidateSite
        Candidate sites.
    out_dir : Path
        Output directory.
    metadata : mapping or None
        Build metadata.
    stem : str
        Output filename stem.

    Returns
    -------
    dict
        Written paths keyed by format.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = candidate_sites_document(sites, metadata=metadata)
    collection = candidate_sites_geojson(sites, metadata=metadata)
    json_path = out_dir / f"{stem}.json"
    geojson_path = out_dir / f"{stem}.geojson"
    meta_path = out_dir / f"{stem}_meta.json"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    geojson_path.write_text(json.dumps(collection, indent=2) + "\n", encoding="utf-8")
    meta_path.write_text(json.dumps(dict(metadata or {}), indent=2) + "\n", encoding="utf-8")
    return {"json": json_path, "geojson": geojson_path, "metadata": meta_path}


def _string(value: object, name: str, *, maximum: int) -> str:
    """Validate a bounded non-empty string."""
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    text = value.strip()
    if not text or len(text) > maximum:
        raise ValueError(f"{name} must be 1 to {maximum} characters")
    return text


def _number(value: object, name: str, minimum: float, maximum: float) -> float:
    """Validate a finite number in a closed range."""
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be numeric") from error
    if not math.isfinite(number) or number < minimum or number > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return number


def _scenario_site(raw: Mapping[str, object]) -> ScenarioSite:
    """Validate one scenario-site mapping."""
    count = raw.get("count", 1)
    if isinstance(count, bool) or not isinstance(count, int) or count < 1 or count > 50:
        raise ValueError("count must be an integer between 1 and 50")
    return ScenarioSite(
        site_id=_string(raw.get("site_id"), "site_id", maximum=120),
        species=_string(raw.get("species"), "species", maximum=80),
        height_m=_number(raw.get("height_m"), "height_m", 0.5, 40.0),
        crown_radius_m=_number(raw.get("crown_radius_m"), "crown_radius_m", 0.25, 20.0),
        count=count,
        cost_cad=_number(raw.get("cost_cad", 0.0), "cost_cad", 0.0, 1_000_000.0),
        water_l_per_year=_number(
            raw.get("water_l_per_year", 0.0), "water_l_per_year", 0.0, 1_000_000.0
        ),
        maintenance=_string(raw.get("maintenance", "unspecified"), "maintenance", maximum=120),
        assumption_source=_string(
            raw.get("assumption_source", "explicit scenario input"),
            "assumption_source",
            maximum=120,
        ),
    )


def scenario_totals(sites: Sequence[ScenarioSite]) -> dict[str, float | int]:
    """Compute scenario totals from sites.

    Parameters
    ----------
    sites : sequence of ScenarioSite
        Scenario sites.

    Returns
    -------
    dict
        Site, tree, cost, and water totals.
    """
    return {
        "sites": len(sites),
        "trees": sum(site.count for site in sites),
        "cost_cad": round(sum(site.cost_cad * site.count for site in sites), 2),
        "water_l_per_year": round(sum(site.water_l_per_year * site.count for site in sites), 2),
    }


def normalize_site_scenario(
    payload: Mapping[str, object],
    *,
    candidate_ids: set[str] | None = None,
) -> SiteScenario:
    """Validate and normalize one site-scenario document.

    Parameters
    ----------
    payload : mapping
        Scenario document.
    candidate_ids : set of str or None
        When provided, every site id must be a known candidate.

    Returns
    -------
    SiteScenario
        Validated scenario with derived totals.

    Raises
    ------
    ValueError
        When the schema, a field, a limit, or a candidate id is invalid.
    """
    if not isinstance(payload, Mapping):
        raise ValueError("scenario must be a mapping")
    if payload.get("schema_version") != SITE_SCENARIO_SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SITE_SCENARIO_SCHEMA_VERSION}")
    scenario_id = _string(payload.get("scenario_id"), "scenario_id", maximum=120)
    label = _string(payload.get("label"), "label", maximum=120)
    created_at = payload.get("created_at", datetime.now(UTC).isoformat())
    created = _string(created_at, "created_at", maximum=40)
    raw_sites = payload.get("sites", [])
    if not isinstance(raw_sites, list):
        raise ValueError("sites must be a list")
    if len(raw_sites) > DEFAULT_MAX_SCENARIO_SITES:
        raise ValueError(f"sites must contain at most {DEFAULT_MAX_SCENARIO_SITES} entries")
    sites: list[ScenarioSite] = []
    seen: set[str] = set()
    for entry in raw_sites:
        if not isinstance(entry, Mapping):
            raise ValueError("each site must be a mapping")
        site = _scenario_site(cast("Mapping[str, object]", entry))
        if site.site_id in seen:
            raise ValueError(f"duplicate site_id: {site.site_id}")
        if candidate_ids is not None and site.site_id not in candidate_ids:
            raise ValueError(f"unknown candidate site_id: {site.site_id}")
        seen.add(site.site_id)
        sites.append(site)
    totals = scenario_totals(sites)
    if cast("int", totals["trees"]) > DEFAULT_MAX_TREES:
        raise ValueError(f"scenario must contain at most {DEFAULT_MAX_TREES} trees")
    settings = payload.get("settings", {})
    metrics = payload.get("metrics", {})
    uncertainty = payload.get("uncertainty", {})
    if not isinstance(settings, Mapping) or not isinstance(metrics, Mapping):
        raise ValueError("settings and metrics must be mappings")
    if not isinstance(uncertainty, Mapping):
        raise ValueError("uncertainty must be a mapping")
    return SiteScenario(
        scenario_id=scenario_id,
        label=label,
        created_at=created,
        sites=tuple(sites),
        settings=dict(settings),
        totals=totals,
        metrics=dict(metrics),
        uncertainty=dict(uncertainty),
    )


def build_site_scenario(
    *,
    label: str,
    sites: Sequence[Mapping[str, object]],
    settings: Mapping[str, object] | None = None,
    metrics: Mapping[str, float | int | None] | None = None,
    uncertainty: Mapping[str, object] | None = None,
    candidate_ids: set[str] | None = None,
    scenario_id: str | None = None,
) -> SiteScenario:
    """Build and validate a new site scenario.

    Parameters
    ----------
    label : str
        Scenario label.
    sites : sequence of mapping
        Scenario-site mappings.
    settings : mapping or None
        Shared evaluation settings.
    metrics : mapping or None
        Optional evaluated metrics.
    uncertainty : mapping or None
        Method and caveat metadata.
    candidate_ids : set of str or None
        Known candidate ids.
    scenario_id : str or None
        Explicit id; otherwise generated.

    Returns
    -------
    SiteScenario
        Validated scenario.
    """
    payload: dict[str, object] = {
        "schema_version": SITE_SCENARIO_SCHEMA_VERSION,
        "scenario_id": scenario_id or f"scenario-{uuid.uuid4().hex[:10]}",
        "label": label,
        "created_at": datetime.now(UTC).isoformat(),
        "settings": dict(settings or {}),
        "sites": [dict(site) for site in sites],
        "metrics": dict(metrics or {}),
        "uncertainty": dict(uncertainty or {}),
    }
    return normalize_site_scenario(payload, candidate_ids=candidate_ids)


__all__ = [
    "CANDIDATE_EVIDENCE",
    "DEFAULT_CELL_SIZE_M",
    "DEFAULT_MAX_CANDIDATE_SITES",
    "DEFAULT_MAX_SCENARIO_SITES",
    "DEFAULT_MAX_SITES_PER_CELL",
    "DEFAULT_MAX_TREES",
    "DEFAULT_SITE_MIN_AREA_M2",
    "SITE_CANDIDATES_SCHEMA_VERSION",
    "SITE_SCENARIO_EVIDENCE",
    "SITE_SCENARIO_SCHEMA_VERSION",
    "CandidateSite",
    "ScenarioSite",
    "SiteScenario",
    "build_site_scenario",
    "candidate_sites_document",
    "candidate_sites_geojson",
    "extract_candidate_sites",
    "normalize_site_scenario",
    "scenario_totals",
    "write_candidate_site_product",
]
