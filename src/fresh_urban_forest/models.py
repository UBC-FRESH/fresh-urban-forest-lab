"""Typed data contracts for the urban-forest lab.

The contracts are deliberately small and serialisable. A dataset is a frozen
``UrbanForestDataset``; an edit is a frozen ``ScenarioEdit``; a projected scenario is a
``ScenarioResult``. Rendering, growth, and the web service all speak these objects, so a
single change to a field is visible everywhere that matters.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from numpy.typing import NDArray

SpeciesGroup = Literal["conifer", "deciduous", "unknown"]
TreeStatus = Literal["alive", "removed", "planted", "dead"]
EditKind = Literal["plant", "remove", "replace", "move"]

DATASET_SCHEMA_VERSION = "fresh-urban-forest.dataset.v1"
SCENARIO_SCHEMA_VERSION = "fresh-urban-forest.scenario.v1"


@dataclass(frozen=True, slots=True)
class TreeRecord:
    """One tree, normalised across inventory sources.

    Attributes
    ----------
    tree_id : str
        Stable identifier within the dataset, usually ``<source>:<source id>``.
    lon : float
        Longitude in WGS84.
    lat : float
        Latitude in WGS84.
    species : str
        Scientific name, cultivar, or source taxon string. May be empty.
    common_name : str
        Common name when the source provides one.
    genus : str
        Genus when it can be parsed, otherwise an empty string.
    dbh_cm : float or None
        Diameter at breast height in centimetres.
    height_m : float or None
        Total tree height in metres.
    crown_width_m : float or None
        Mean crown width in metres.
    crown_ratio : float
        Live-crown ratio, 0 to 1.
    status : str
        One of ``alive``, ``removed``, ``planted``, or ``dead``.
    source : str
        Inventory source identifier.
    source_date : str or None
        ISO date or year when the record was measured.
    native : bool or None
        Whether the source labels the species as native.
    x_m : float or None
        Projected easting in the dataset CRS.
    y_m : float or None
        Projected northing in the dataset CRS.
    elevation_m : float or None
        Ground elevation in metres.
    lidar_height_m : float or None
        LiDAR canopy height sampled at the tree location.
    attributes : mapping of str to str
        Extra source attributes that should survive a round trip.
    """

    tree_id: str
    lon: float
    lat: float
    species: str = ""
    common_name: str = ""
    genus: str = ""
    dbh_cm: float | None = None
    height_m: float | None = None
    crown_width_m: float | None = None
    crown_ratio: float = 0.5
    status: TreeStatus = "alive"
    source: str = "unknown"
    source_date: str | None = None
    native: bool | None = None
    x_m: float | None = None
    y_m: float | None = None
    elevation_m: float | None = None
    lidar_height_m: float | None = None
    attributes: Mapping[str, str] = field(default_factory=dict)

    @property
    def label(self) -> str:
        """Return the most informative human-readable name available.

        Returns
        -------
        str
            The common name, then the species, then the tree identifier.
        """
        return self.common_name or self.species or self.tree_id


@dataclass(frozen=True, slots=True)
class Building:
    """A building footprint used for planting constraints and 3D context.

    Attributes
    ----------
    building_id : str
        Source identifier.
    name : str
        Human-readable name.
    height_m : float
        Extrusion height in metres.
    rings : tuple of tuple of tuple of float
        Exterior ring coordinates in WGS84 ``(lon, lat)`` pairs.
    """

    building_id: str
    name: str
    height_m: float
    rings: tuple[tuple[tuple[float, float], ...], ...]


@dataclass(frozen=True, slots=True)
class TerrainGrid:
    """A regular terrain and canopy-height grid on a projected CRS.

    Attributes
    ----------
    crs : str
        Projected CRS, for example ``EPSG:3157``.
    bounds : tuple of float
        ``(left, bottom, right, top)`` in the projected CRS.
    width : int
        Number of columns.
    height : int
        Number of rows.
    elevation : numpy.ndarray
        Ground elevation, shape ``(height, width)``.
    canopy_height : numpy.ndarray or None
        Canopy height above ground, shape ``(height, width)``.
    """

    crs: str
    bounds: tuple[float, float, float, float]
    width: int
    height: int
    elevation: NDArray[np.float32]
    canopy_height: NDArray[np.float32] | None = None


@dataclass(frozen=True, slots=True)
class CanopyMetrics:
    """Summary of canopy structure and composition for one point in time.

    Attributes
    ----------
    tree_count : int
        Number of live trees.
    species_count : int
        Number of distinct species labels.
    native_fraction : float
        Share of live trees labelled native, 0 to 1.
    canopy_cover_pct : float
        Fraction of the analysis area covered by canopy at least 2 m tall, in percent.
    canopy_volume_m3 : float
        Summed crown volume of live trees in cubic metres.
    mean_height_m : float
        Mean live-tree height.
    p95_height_m : float
        95th percentile live-tree height.
    total_carbon_kg : float
        Estimated above-ground carbon mass in kilograms.
    shannon_index : float
        Shannon diversity of the species composition.
    size_classes : tuple of tuple of str and int
        Counts by diameter class, ordered smallest first.
    species_composition : tuple of tuple of str and int
        Counts by species, ordered largest first.
    """

    tree_count: int
    species_count: int
    native_fraction: float
    canopy_cover_pct: float
    canopy_volume_m3: float
    mean_height_m: float
    p95_height_m: float
    total_carbon_kg: float
    shannon_index: float
    size_classes: tuple[tuple[str, int], ...] = ()
    species_composition: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True, slots=True)
class SourceRecord:
    """Provenance for one input source.

    Attributes
    ----------
    source_id : str
        Catalog identifier.
    title : str
        Human-readable title.
    publisher : str
        Organisation that publishes the source.
    url : str
        Landing page or direct URL.
    licence : str
        Licence identifier or short statement.
    access_mode : str
        One of ``direct_http``, ``catalog``, or ``manual``.
    retrieved_utc : str
        ISO timestamp when the source was retrieved or registered.
    checksum : str
        ``sha256:<hex>`` for downloaded payloads, otherwise an empty string.
    notes : str
        Caveats and attribution notes.
    """

    source_id: str
    title: str
    publisher: str
    url: str
    licence: str
    access_mode: str
    retrieved_utc: str
    checksum: str = ""
    notes: str = ""


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    """The portable record that describes a built dataset.

    Attributes
    ----------
    schema_version : str
        Dataset schema identifier.
    dataset_id : str
        Stable dataset identifier.
    name : str
        Human-readable dataset name.
    generated_utc : str
        ISO timestamp when the dataset was written.
    crs : str
        Projected CRS used for metric calculations.
    bounds : tuple of float
        ``(left, bottom, right, top)`` in the projected CRS.
    tree_count : int
        Number of tree records.
    sources : tuple of SourceRecord
        Provenance records for every input.
    metrics : CanopyMetrics
        Metrics at the inventory date.
    files : mapping of str to str
        Repository-relative paths of dataset files.
    """

    schema_version: str
    dataset_id: str
    name: str
    generated_utc: str
    crs: str
    bounds: tuple[float, float, float, float]
    tree_count: int
    sources: tuple[SourceRecord, ...]
    metrics: CanopyMetrics
    files: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class UrbanForestDataset:
    """A complete urban-forest dataset ready for analysis and rendering.

    Attributes
    ----------
    manifest : DatasetManifest
        Portable metadata and provenance.
    trees : tuple of TreeRecord
        Normalised tree inventory.
    terrain : TerrainGrid
        Terrain and canopy-height grid.
    buildings : tuple of Building
        Building footprints for context and constraints.
    boundary : tuple of tuple of float
        Campus boundary ring in WGS84 ``(lon, lat)`` pairs.
    """

    manifest: DatasetManifest
    trees: tuple[TreeRecord, ...]
    terrain: TerrainGrid
    buildings: tuple[Building, ...] = ()
    boundary: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True, slots=True)
class ScenarioEdit:
    """One reversible change to a tree population.

    Attributes
    ----------
    edit_id : str
        Stable identifier for the edit.
    kind : str
        One of ``plant``, ``remove``, ``replace``, or ``move``.
    tree_id : str
        Target tree identifier. For a plant, the identifier of the new tree.
    lon : float or None
        Longitude for a plant, replace, or move.
    lat : float or None
        Latitude for a plant, replace, or move.
    species : str or None
        Species for a plant or replacement.
    common_name : str or None
        Common name for a plant or replacement.
    dbh_cm : float or None
        Initial diameter for a planted tree.
    height_m : float or None
        Initial height for a planted tree.
    crown_width_m : float or None
        Initial crown width for a planted tree.
    note : str
        Free-text rationale.
    """

    edit_id: str
    kind: EditKind
    tree_id: str
    lon: float | None = None
    lat: float | None = None
    species: str | None = None
    common_name: str | None = None
    dbh_cm: float | None = None
    height_m: float | None = None
    crown_width_m: float | None = None
    note: str = ""


@dataclass(frozen=True, slots=True)
class Scenario:
    """A named sequence of edits against a base dataset.

    Attributes
    ----------
    schema_version : str
        Scenario schema identifier.
    scenario_id : str
        Stable identifier.
    name : str
        Human-readable name.
    created_utc : str
        ISO timestamp when the scenario was created.
    base_dataset_id : str
        Dataset identifier the scenario applies to.
    years : int
        Projection horizon in years.
    edits : tuple of ScenarioEdit
        Edits in application order.
    revision : int
        Monotonic revision for optimistic concurrency.
    """

    scenario_id: str
    name: str
    created_utc: str
    base_dataset_id: str
    years: int
    edits: tuple[ScenarioEdit, ...] = ()
    revision: int = 0
    schema_version: str = SCENARIO_SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    """The projected outcome of a scenario.

    Attributes
    ----------
    scenario : Scenario
        The scenario that produced the result.
    metrics_by_year : tuple of tuple of int and CanopyMetrics
        Metrics for year zero and every projected year.
    final_trees : tuple of TreeRecord
        The tree population at the end of the projection.
    cost : float
        Estimated implementation cost in Canadian dollars.
    score : float
        Decision-support score, higher is better.
    notes : tuple of str
        Assumptions and caveats.
    """

    scenario: Scenario
    metrics_by_year: tuple[tuple[int, CanopyMetrics], ...]
    final_trees: tuple[TreeRecord, ...]
    cost: float
    score: float
    notes: tuple[str, ...] = ()


def metrics_to_dict(metrics: CanopyMetrics) -> dict[str, object]:
    """Convert metrics to a JSON-safe dictionary.

    Parameters
    ----------
    metrics : CanopyMetrics
        Metrics to convert.

    Returns
    -------
    dict
        A dictionary with lists in place of tuples.
    """
    return {
        "tree_count": metrics.tree_count,
        "species_count": metrics.species_count,
        "native_fraction": metrics.native_fraction,
        "canopy_cover_pct": metrics.canopy_cover_pct,
        "canopy_volume_m3": metrics.canopy_volume_m3,
        "mean_height_m": metrics.mean_height_m,
        "p95_height_m": metrics.p95_height_m,
        "total_carbon_kg": metrics.total_carbon_kg,
        "shannon_index": metrics.shannon_index,
        "size_classes": [list(item) for item in metrics.size_classes],
        "species_composition": [list(item) for item in metrics.species_composition],
    }


def metrics_from_dict(data: Mapping[str, object]) -> CanopyMetrics:
    """Build metrics from a mapping produced by :func:`metrics_to_dict`.

    Parameters
    ----------
    data : mapping
        Mapping with metric keys.

    Returns
    -------
    CanopyMetrics
        The reconstructed metrics.
    """
    return CanopyMetrics(
        tree_count=_as_int(data.get("tree_count")),
        species_count=_as_int(data.get("species_count")),
        native_fraction=_as_float(data.get("native_fraction")),
        canopy_cover_pct=_as_float(data.get("canopy_cover_pct")),
        canopy_volume_m3=_as_float(data.get("canopy_volume_m3")),
        mean_height_m=_as_float(data.get("mean_height_m")),
        p95_height_m=_as_float(data.get("p95_height_m")),
        total_carbon_kg=_as_float(data.get("total_carbon_kg")),
        shannon_index=_as_float(data.get("shannon_index")),
        size_classes=_pairs(data.get("size_classes")),
        species_composition=_pairs(data.get("species_composition")),
    )


def tree_to_dict(tree: TreeRecord) -> dict[str, object]:
    """Convert a tree record to a JSON-safe dictionary.

    Parameters
    ----------
    tree : TreeRecord
        Tree to convert.

    Returns
    -------
    dict
        A flat dictionary with source attributes preserved.
    """
    return {
        "tree_id": tree.tree_id,
        "lon": tree.lon,
        "lat": tree.lat,
        "species": tree.species,
        "common_name": tree.common_name,
        "genus": tree.genus,
        "dbh_cm": tree.dbh_cm,
        "height_m": tree.height_m,
        "crown_width_m": tree.crown_width_m,
        "crown_ratio": tree.crown_ratio,
        "status": tree.status,
        "source": tree.source,
        "source_date": tree.source_date,
        "native": tree.native,
        "x_m": tree.x_m,
        "y_m": tree.y_m,
        "elevation_m": tree.elevation_m,
        "lidar_height_m": tree.lidar_height_m,
        "attributes": dict(tree.attributes),
    }


def tree_from_dict(data: Mapping[str, object]) -> TreeRecord:
    """Build a tree record from a mapping produced by :func:`tree_to_dict`.

    Parameters
    ----------
    data : mapping
        Mapping with tree keys.

    Returns
    -------
    TreeRecord
        The reconstructed tree.
    """
    raw_attributes = data.get("attributes", {})
    attributes = (
        {str(key): str(value) for key, value in raw_attributes.items()}
        if isinstance(raw_attributes, Mapping)
        else {}
    )
    return TreeRecord(
        tree_id=_as_str(data.get("tree_id")),
        lon=_as_float(data.get("lon")),
        lat=_as_float(data.get("lat")),
        species=_as_str(data.get("species")),
        common_name=_as_str(data.get("common_name")),
        genus=_as_str(data.get("genus")),
        dbh_cm=_optional_float(data.get("dbh_cm")),
        height_m=_optional_float(data.get("height_m")),
        crown_width_m=_optional_float(data.get("crown_width_m")),
        crown_ratio=_as_float(data.get("crown_ratio"), 0.5),
        status=_tree_status(data.get("status")),
        source=_as_str(data.get("source")) or "unknown",
        source_date=_optional_str(data.get("source_date")),
        native=_optional_bool(data.get("native")),
        x_m=_optional_float(data.get("x_m")),
        y_m=_optional_float(data.get("y_m")),
        elevation_m=_optional_float(data.get("elevation_m")),
        lidar_height_m=_optional_float(data.get("lidar_height_m")),
        attributes=attributes,
    )


def edit_to_dict(edit: ScenarioEdit) -> dict[str, object]:
    """Convert a scenario edit to a JSON-safe dictionary.

    Parameters
    ----------
    edit : ScenarioEdit
        Edit to convert.

    Returns
    -------
    dict
        A flat dictionary.
    """
    return {
        "edit_id": edit.edit_id,
        "kind": edit.kind,
        "tree_id": edit.tree_id,
        "lon": edit.lon,
        "lat": edit.lat,
        "species": edit.species,
        "common_name": edit.common_name,
        "dbh_cm": edit.dbh_cm,
        "height_m": edit.height_m,
        "crown_width_m": edit.crown_width_m,
        "note": edit.note,
    }


def edit_from_dict(data: Mapping[str, object]) -> ScenarioEdit:
    """Build a scenario edit from a mapping produced by :func:`edit_to_dict`.

    Parameters
    ----------
    data : mapping
        Mapping with edit keys.

    Returns
    -------
    ScenarioEdit
        The reconstructed edit.
    """
    kind = str(data.get("kind", "plant"))
    if kind not in {"plant", "remove", "replace", "move"}:
        raise ValueError(f"unknown edit kind: {kind}")
    return ScenarioEdit(
        edit_id=_as_str(data.get("edit_id")),
        kind=kind,  # type: ignore[arg-type]
        tree_id=_as_str(data.get("tree_id")),
        lon=_optional_float(data.get("lon")),
        lat=_optional_float(data.get("lat")),
        species=_optional_str(data.get("species")),
        common_name=_optional_str(data.get("common_name")),
        dbh_cm=_optional_float(data.get("dbh_cm")),
        height_m=_optional_float(data.get("height_m")),
        crown_width_m=_optional_float(data.get("crown_width_m")),
        note=_as_str(data.get("note")),
    )


def scenario_to_dict(scenario: Scenario) -> dict[str, object]:
    """Convert a scenario to a JSON-safe dictionary.

    Parameters
    ----------
    scenario : Scenario
        Scenario to convert.

    Returns
    -------
    dict
        A dictionary with an ``edits`` list.
    """
    return {
        "schema_version": scenario.schema_version,
        "scenario_id": scenario.scenario_id,
        "name": scenario.name,
        "created_utc": scenario.created_utc,
        "base_dataset_id": scenario.base_dataset_id,
        "years": scenario.years,
        "revision": scenario.revision,
        "edits": [edit_to_dict(edit) for edit in scenario.edits],
    }


def scenario_from_dict(data: Mapping[str, object]) -> Scenario:
    """Build a scenario from a mapping produced by :func:`scenario_to_dict`.

    Parameters
    ----------
    data : mapping
        Mapping with scenario keys.

    Returns
    -------
    Scenario
        The reconstructed scenario.
    """
    raw_edits = data.get("edits", [])
    edits = (
        tuple(edit_from_dict(item) for item in raw_edits if isinstance(item, Mapping))
        if isinstance(raw_edits, list)
        else ()
    )
    return Scenario(
        scenario_id=_as_str(data.get("scenario_id")),
        name=_as_str(data.get("name")) or "Untitled scenario",
        created_utc=_as_str(data.get("created_utc")),
        base_dataset_id=_as_str(data.get("base_dataset_id")),
        years=_as_int(data.get("years"), 25),
        edits=edits,
        revision=_as_int(data.get("revision")),
        schema_version=_as_str(data.get("schema_version")) or SCENARIO_SCHEMA_VERSION,
    )


def _as_float(value: object, default: float = 0.0) -> float:
    """Convert a JSON value to a float with a default.

    Parameters
    ----------
    value : object
        Value to convert.
    default : float
        Value returned when conversion fails.

    Returns
    -------
    float
        The converted value.
    """
    if isinstance(value, (int, float, str)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
    return default


def _as_int(value: object, default: int = 0) -> int:
    """Convert a JSON value to an integer with a default.

    Parameters
    ----------
    value : object
        Value to convert.
    default : int
        Value returned when conversion fails.

    Returns
    -------
    int
        The converted value.
    """
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, str)):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default
    return default


def _as_str(value: object) -> str:
    """Convert a JSON value to a stripped string.

    Parameters
    ----------
    value : object
        Value to convert.

    Returns
    -------
    str
        The string, or an empty string for ``None``.
    """
    return "" if value is None else str(value).strip()


def _pairs(value: object) -> tuple[tuple[str, int], ...]:
    """Convert a JSON list of two-item lists to a tuple of key-count pairs.

    Parameters
    ----------
    value : object
        Candidate list.

    Returns
    -------
    tuple of tuple of str and int
        The converted pairs.
    """
    if not isinstance(value, list):
        return ()
    pairs: list[tuple[str, int]] = []
    for item in value:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            pairs.append((_as_str(item[0]), _as_int(item[1])))
    return tuple(pairs)


def _optional_float(value: object) -> float | None:
    """Convert an optional value to a float.

    Parameters
    ----------
    value : object
        Value to convert.

    Returns
    -------
    float or None
        The converted value, or ``None`` for an empty, null, or invalid value.
    """
    if value is None or value == "":
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _optional_str(value: object) -> str | None:
    """Convert an optional value to a non-empty string.

    Parameters
    ----------
    value : object
        Value to convert.

    Returns
    -------
    str or None
        The stripped string, or ``None`` when empty.
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_bool(value: object) -> bool | None:
    """Convert an optional value to a boolean.

    Parameters
    ----------
    value : object
        Value to convert.

    Returns
    -------
    bool or None
        ``True`` or ``False`` when the value is recognisable, otherwise ``None``.
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "t", "yes", "y", "1"}:
        return True
    if text in {"false", "f", "no", "n", "0"}:
        return False
    return None


def _tree_status(value: object) -> TreeStatus:
    """Normalise a tree status.

    Parameters
    ----------
    value : object
        Status value.

    Returns
    -------
    str
        One of ``alive``, ``removed``, ``planted``, or ``dead``.
    """
    text = str(value or "alive").strip().lower()
    if text in {"alive", "live", "existing"}:
        return "alive"
    if text in {"removed", "cut", "deleted"}:
        return "removed"
    if text in {"planted", "new"}:
        return "planted"
    if text in {"dead", "declining"}:
        return "dead"
    return "alive"
