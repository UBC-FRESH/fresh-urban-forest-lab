"""A transparent bird-habitat index from 3D canopy structure.

This is a prior-driven screening model, not a bird survey. It computes structural metrics
from the tree population and links them to guild suitability and a relative-abundance
index. Absolute density and survival need local field data.
"""

from __future__ import annotations

import csv
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from fresh_urban_forest.allometry import (
    is_native_species,
    tree_crown_volume_m3,
)
from fresh_urban_forest.evidence import Evidence, evidence
from fresh_urban_forest.models import TerrainGrid, TreeRecord

HABITAT_EVIDENCE = evidence(
    "prior",
    "canopy-structure-habitat-index",
    uncertainty=(
        "Structural guild weights and abundance coefficients are literature/expert priors; "
        "they are not calibrated to local bird surveys."
    ),
    source="LiDAR/tree structural metrics plus transparent guild priors",
)
GUILD_EVIDENCE = evidence(
    "prior",
    "guild-suitability",
    uncertainty="Guild suitability is a relative screening index, not a density estimate.",
    source="Published habitat-structure associations and expert priors",
)


@dataclass(frozen=True, slots=True)
class HabitatMetrics:
    """3D canopy metrics used by the bird layer.

    Attributes
    ----------
    tree_count : int
        Live-tree count.
    native_fraction : float
        Share of live trees native or labelled native.
    mean_height_m : float
        Mean live-tree height.
    p95_height_m : float
        95th percentile height.
    canopy_cover_pct : float
        Raster canopy cover at least 2 m tall.
    gap_fraction : float
        One minus canopy cover fraction.
    vertical_complexity : float
        Normalised standard deviation of crown-centre heights.
    foliage_height_diversity : float
        Shannon diversity of crown volume across height bands, normalised by log(bands).
    layering_count : int
        Height bands with at least five percent of crown volume.
    size_diversity : float
        Normalised Shannon diversity of DBH size classes.
    habitat_score : float
        Weighted composite from zero to one.
    evidence : Evidence
        Method and tier.
    """

    tree_count: int
    native_fraction: float
    mean_height_m: float
    p95_height_m: float
    canopy_cover_pct: float
    gap_fraction: float
    vertical_complexity: float
    foliage_height_diversity: float
    layering_count: int
    size_diversity: float
    habitat_score: float
    evidence: Evidence

    def to_dict(self) -> dict[str, object]:
        """Convert the metrics to JSON-safe values.

        Returns
        -------
        dict
            Metrics and evidence.
        """
        return {
            "tree_count": self.tree_count,
            "native_fraction": round(self.native_fraction, 4),
            "mean_height_m": round(self.mean_height_m, 3),
            "p95_height_m": round(self.p95_height_m, 3),
            "canopy_cover_pct": round(self.canopy_cover_pct, 3),
            "gap_fraction": round(self.gap_fraction, 4),
            "vertical_complexity": round(self.vertical_complexity, 4),
            "foliage_height_diversity": round(self.foliage_height_diversity, 4),
            "layering_count": self.layering_count,
            "size_diversity": round(self.size_diversity, 4),
            "habitat_score": round(self.habitat_score, 4),
            "evidence": self.evidence.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class BirdGuild:
    """A guild-level habitat and demographic prior.

    Attributes
    ----------
    name : str
        Machine name.
    label : str
        Human label.
    canopy_weight : float
        Weight on canopy height/structure.
    native_weight : float
        Weight on native-tree share.
    gap_weight : float
        Weight on open/gap habitat.
    base_abundance : float
        Relative abundance coefficient, not a density.
    survival_juvenile : float
        Juvenile annual survival prior.
    survival_adult : float
        Adult annual survival prior.
    fecundity : float
        Fledglings per adult per year prior.
    evidence : Evidence
        Method and tier.
    """

    name: str
    label: str
    canopy_weight: float
    native_weight: float
    gap_weight: float
    base_abundance: float
    survival_juvenile: float
    survival_adult: float
    fecundity: float
    evidence: Evidence

    def to_dict(self) -> dict[str, object]:
        """Convert the guild to JSON-safe values.

        Returns
        -------
        dict
            Guild traits and evidence.
        """
        return {
            "name": self.name,
            "label": self.label,
            "canopy_weight": self.canopy_weight,
            "native_weight": self.native_weight,
            "gap_weight": self.gap_weight,
            "base_abundance": self.base_abundance,
            "survival_juvenile": self.survival_juvenile,
            "survival_adult": self.survival_adult,
            "fecundity": self.fecundity,
            "evidence": self.evidence.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class GuildHabitat:
    """Habitat suitability and relative abundance for one guild.

    Attributes
    ----------
    guild : BirdGuild
        Guild traits.
    suitability : float
        Suitability from zero to one.
    relative_abundance_index : float
        Relative index, not birds per hectare or absolute density.
    limiting_factors : tuple of str
        Structural factors below the suitability threshold.
    evidence : Evidence
        Method and tier.
    """

    guild: BirdGuild
    suitability: float
    relative_abundance_index: float
    limiting_factors: tuple[str, ...]
    evidence: Evidence

    def to_dict(self) -> dict[str, object]:
        """Convert the guild habitat result to JSON-safe values.

        Returns
        -------
        dict
            Guild, suitability, relative index, and limitations.
        """
        return {
            "guild": self.guild.to_dict(),
            "suitability": round(self.suitability, 4),
            "relative_abundance_index": round(self.relative_abundance_index, 4),
            "limiting_factors": list(self.limiting_factors),
            "evidence": self.evidence.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class BirdObservation:
    """Optional bird observation record.

    Attributes
    ----------
    species : str
        Species label.
    lon : float
        Longitude.
    lat : float
        Latitude.
    count : float
        Observed count or relative index.
    guild : str
        Optional guild assignment.
    """

    species: str
    lon: float
    lat: float
    count: float
    guild: str = ""


GUILDS: tuple[BirdGuild, ...] = (
    BirdGuild(
        "canopy_insectivores",
        "Canopy insectivores",
        canopy_weight=0.55,
        native_weight=0.25,
        gap_weight=0.20,
        base_abundance=12.0,
        survival_juvenile=0.35,
        survival_adult=0.72,
        fecundity=0.85,
        evidence=GUILD_EVIDENCE,
    ),
    BirdGuild(
        "cavity_nesters",
        "Cavity nesters",
        canopy_weight=0.45,
        native_weight=0.40,
        gap_weight=0.15,
        base_abundance=5.0,
        survival_juvenile=0.42,
        survival_adult=0.78,
        fecundity=0.55,
        evidence=GUILD_EVIDENCE,
    ),
    BirdGuild(
        "ground_foragers",
        "Ground foragers",
        canopy_weight=0.25,
        native_weight=0.25,
        gap_weight=0.50,
        base_abundance=9.0,
        survival_juvenile=0.28,
        survival_adult=0.64,
        fecundity=1.20,
        evidence=GUILD_EVIDENCE,
    ),
    BirdGuild(
        "migrants",
        "Migrants",
        canopy_weight=0.50,
        native_weight=0.30,
        gap_weight=0.20,
        base_abundance=7.0,
        survival_juvenile=0.24,
        survival_adult=0.60,
        fecundity=1.05,
        evidence=GUILD_EVIDENCE,
    ),
    BirdGuild(
        "urban_adapters",
        "Urban adapters",
        canopy_weight=0.20,
        native_weight=0.10,
        gap_weight=0.70,
        base_abundance=20.0,
        survival_juvenile=0.48,
        survival_adult=0.80,
        fecundity=1.50,
        evidence=GUILD_EVIDENCE,
    ),
)


def habitat_metrics(
    trees: tuple[TreeRecord, ...] | list[TreeRecord], terrain: TerrainGrid
) -> HabitatMetrics:
    """Calculate structural habitat metrics from a tree population.

    Parameters
    ----------
    trees : sequence of TreeRecord
        Tree population.
    terrain : TerrainGrid
        Terrain and canopy grid.

    Returns
    -------
    HabitatMetrics
        Structural metrics and composite score.
    """
    live = [tree for tree in trees if tree.status not in {"removed", "dead"}]
    heights = np.asarray([float(tree.height_m or 0.0) for tree in live], dtype=np.float64)
    heights = heights[heights > 0.0]
    native = [
        bool(tree.native) if tree.native is not None else is_native_species(tree.species)
        for tree in live
    ]
    native_fraction = sum(native) / max(len(live), 1)
    mean_height = float(np.mean(heights)) if heights.size else 0.0
    p95_height = float(np.percentile(heights, 95)) if heights.size else 0.0
    canopy_cover = _canopy_cover(terrain)
    gap_fraction = 1.0 - canopy_cover / 100.0
    vertical_complexity = float(np.std(heights) / max(mean_height, 1e-9)) if heights.size else 0.0
    vertical_complexity = max(0.0, min(1.0, vertical_complexity))
    fhd, layering = _foliage_height_diversity(live)
    size_diversity = _size_diversity(live)
    canopy_score = min(1.0, p95_height / 30.0)
    score = (
        0.20 * canopy_score
        + 0.18 * fhd
        + 0.14 * min(1.0, layering / 4.0)
        + 0.16 * vertical_complexity
        + 0.12 * native_fraction
        + 0.10 * size_diversity
        + 0.10 * (1.0 - gap_fraction)
    )
    return HabitatMetrics(
        tree_count=len(live),
        native_fraction=native_fraction,
        mean_height_m=mean_height,
        p95_height_m=p95_height,
        canopy_cover_pct=canopy_cover,
        gap_fraction=gap_fraction,
        vertical_complexity=vertical_complexity,
        foliage_height_diversity=fhd,
        layering_count=layering,
        size_diversity=size_diversity,
        habitat_score=max(0.0, min(1.0, score)),
        evidence=HABITAT_EVIDENCE,
    )


def guild_habitat(metrics: HabitatMetrics, guild: BirdGuild) -> GuildHabitat:
    """Calculate guild suitability and a relative-abundance index.

    Parameters
    ----------
    metrics : HabitatMetrics
        Structural metrics.
    guild : BirdGuild
        Guild traits.

    Returns
    -------
    GuildHabitat
        Suitability, relative index, and limiting factors.
    """
    canopy = min(
        1.0,
        0.45 * min(metrics.p95_height_m / 30.0, 1.0)
        + 0.30 * metrics.foliage_height_diversity
        + 0.25 * min(metrics.layering_count / 4.0, 1.0),
    )
    native = metrics.native_fraction
    openness = metrics.gap_fraction
    suitability = (
        guild.canopy_weight * canopy + guild.native_weight * native + guild.gap_weight * openness
    )
    suitability = max(0.0, min(1.0, suitability))
    components = {
        "canopy structure": canopy,
        "native tree share": native,
        "open/gap habitat": openness,
    }
    limiting = tuple(
        factor
        for factor, value in sorted(components.items(), key=lambda item: item[1])
        if value < 0.4
    )
    return GuildHabitat(
        guild=guild,
        suitability=suitability,
        relative_abundance_index=guild.base_abundance * suitability,
        limiting_factors=limiting,
        evidence=GUILD_EVIDENCE,
    )


def bird_report(
    trees: tuple[TreeRecord, ...] | list[TreeRecord],
    terrain: TerrainGrid,
) -> dict[str, object]:
    """Build a baseline bird-habitat report.

    Parameters
    ----------
    trees : sequence of TreeRecord
        Tree population.
    terrain : TerrainGrid
        Terrain and canopy grid.

    Returns
    -------
    dict
        Structural metrics and one result per guild.
    """
    metrics = habitat_metrics(trees, terrain)
    guilds = [guild_habitat(metrics, guild) for guild in GUILDS]
    return {
        "metrics": metrics.to_dict(),
        "guilds": [result.to_dict() for result in guilds],
        "evidence": HABITAT_EVIDENCE.to_dict(),
        "caveat": "Relative abundance is a screening index, not a density or survival estimate.",
    }


def load_observations_csv(path: Path) -> tuple[BirdObservation, ...]:
    """Load optional bird observations from a CSV.

    Parameters
    ----------
    path : Path
        CSV with ``species,lon,lat,count`` and optional ``guild``.

    Returns
    -------
    tuple of BirdObservation
        Parsed observations.

    Raises
    ------
    ValueError
        When a numeric field is invalid.
    """
    observations: list[BirdObservation] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                observations.append(
                    BirdObservation(
                        species=str(row.get("species", "")).strip(),
                        lon=float(row.get("lon", 0.0)),
                        lat=float(row.get("lat", 0.0)),
                        count=float(row.get("count", 1.0)),
                        guild=str(row.get("guild", "")).strip(),
                    )
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid observation row: {row}") from exc
    return tuple(observations)


def write_bird_report(payload: Mapping[str, object], path: Path) -> Path:
    """Write a bird-habitat report.

    Parameters
    ----------
    payload : mapping
        Report payload.
    path : Path
        Destination JSON.

    Returns
    -------
    Path
        The written path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), indent=2) + "\n", encoding="utf-8")
    return path


def _canopy_cover(terrain: TerrainGrid) -> float:
    """Calculate raster canopy cover."""
    if terrain.canopy_height is None:
        return 0.0
    canopy = np.asarray(terrain.canopy_height, dtype=np.float64)
    valid = np.isfinite(canopy)
    if not np.any(valid):
        return 0.0
    return float(100.0 * np.count_nonzero(canopy[valid] >= 2.0) / np.count_nonzero(valid))


def _foliage_height_diversity(trees: list[TreeRecord]) -> tuple[float, int]:
    """Calculate crown-volume diversity across height bands."""
    bands = np.zeros(6, dtype=np.float64)
    for tree in trees:
        height = float(tree.height_m or 0.0)
        volume = tree_crown_volume_m3(tree)
        if height <= 0.0 or volume <= 0.0:
            continue
        index = (
            0
            if height < 2.0
            else 1
            if height < 5.0
            else 2
            if height < 10.0
            else 3
            if height < 15.0
            else 4
            if height < 20.0
            else 5
        )
        bands[index] += volume
    total = float(np.sum(bands))
    if total <= 0.0:
        return (0.0, 0)
    proportions = bands[bands > 0.0] / total
    entropy = float(-np.sum(proportions * np.log(proportions)))
    diversity = entropy / math.log(len(bands))
    layering = int(np.count_nonzero(bands / total >= 0.05))
    return (max(0.0, min(1.0, diversity)), layering)


def _size_diversity(trees: list[TreeRecord]) -> float:
    """Calculate Shannon diversity across DBH size classes."""
    bins = [0, 5, 10, 20, 30, 50, 80, 120]
    counts = [0 for _ in range(len(bins) - 1)]
    for tree in trees:
        dbh = float(tree.dbh_cm or 0.0)
        if dbh <= 0.0:
            continue
        index = 0
        for position in range(len(bins) - 1):
            if bins[position] <= dbh < bins[position + 1]:
                index = position
                break
        else:
            index = len(counts) - 1
        counts[index] += 1
    total = sum(counts)
    if total <= 0:
        return 0.0
    proportions = [count / total for count in counts if count > 0]
    entropy = -sum(value * math.log(value) for value in proportions)
    return max(0.0, min(1.0, entropy / math.log(len(counts))))
