"""Species traits and site-fit scoring for urban planting decisions.

The trait table is a transparent, source-labelled prior for common Vancouver and Pacific
Northwest species. It is not a local field calibration. A site fit is a screening score:
it identifies the limiting factor and the evidence behind it, not a guarantee of survival.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

from fresh_urban_forest.allometry import species_group
from fresh_urban_forest.evidence import Evidence, evidence
from fresh_urban_forest.models import SpeciesGroup

FIT_EVIDENCE = evidence(
    "prior",
    "trait-site-match",
    uncertainty="Expert-assigned trait scores; replace with local species trials and climate data.",
    source=(
        "Transparent species trait table; see "
        "notes/reference/literature-review-shade-optimization-biodiversity.md"
    ),
)


@dataclass(frozen=True, slots=True)
class SpeciesProfile:
    """Trait profile for one species or species group.

    Attributes
    ----------
    name : str
        Scientific or group name.
    common_name : str
        Common name.
    group : str
        Conifer, deciduous, or unknown.
    light_demand : int
        Light demand from 1 (shade tolerant) to 5 (full sun).
    drought_tolerance : int
        Drought tolerance from 1 (low) to 5 (high).
    water_use : float
        Relative water-use coefficient, where 1 is average.
    min_soil_volume_m3 : float
        Minimum soil volume for a viable planting site.
    mature_height_m : float
        Typical mature height.
    mature_crown_width_m : float
        Typical mature crown width.
    native : bool
        Whether the species is native to the Pacific Northwest.
    salt_tolerance : int
        Salt tolerance from 1 to 5.
    heat_tolerance : int
        Heat tolerance from 1 to 5.
    flood_tolerance : int
        Flood tolerance from 1 to 5.
    allergen_risk : int
        Allergen risk from 1 to 5.
    bvoc_risk : int
        Biogenic volatile organic compound risk from 1 to 5.
    source : str
        Trait source note.
    confidence : str
        Confidence label.
    """

    name: str
    common_name: str
    group: SpeciesGroup
    light_demand: int
    drought_tolerance: int
    water_use: float
    min_soil_volume_m3: float
    mature_height_m: float
    mature_crown_width_m: float
    native: bool
    salt_tolerance: int
    heat_tolerance: int
    flood_tolerance: int
    allergen_risk: int
    bvoc_risk: int
    source: str
    confidence: str

    def to_dict(self) -> dict[str, object]:
        """Convert the profile to a JSON-safe dictionary.

        Returns
        -------
        dict
            Every trait and its source.
        """
        return {
            "name": self.name,
            "common_name": self.common_name,
            "group": self.group,
            "light_demand": self.light_demand,
            "drought_tolerance": self.drought_tolerance,
            "water_use": self.water_use,
            "min_soil_volume_m3": self.min_soil_volume_m3,
            "mature_height_m": self.mature_height_m,
            "mature_crown_width_m": self.mature_crown_width_m,
            "native": self.native,
            "salt_tolerance": self.salt_tolerance,
            "heat_tolerance": self.heat_tolerance,
            "flood_tolerance": self.flood_tolerance,
            "allergen_risk": self.allergen_risk,
            "bvoc_risk": self.bvoc_risk,
            "source": self.source,
            "confidence": self.confidence,
        }


@dataclass(frozen=True, slots=True)
class SpeciesFit:
    """The match between one species and one site.

    Attributes
    ----------
    species : str
        Species name.
    score : float
        Weighted fit score from zero to one.
    light_score : float
        Light match.
    water_score : float
        Water match.
    soil_score : float
        Soil-volume match.
    heat_score : float
        Heat match.
    space_score : float
        Space match.
    limiting_factors : tuple of str
        Factors below the limiting threshold, worst first.
    evidence : Evidence
        Method and tier.
    """

    species: str
    score: float
    light_score: float
    water_score: float
    soil_score: float
    heat_score: float
    space_score: float
    limiting_factors: tuple[str, ...]
    evidence: Evidence

    def to_dict(self) -> dict[str, object]:
        """Convert the fit to a JSON-safe dictionary.

        Returns
        -------
        dict
            Scores, limiting factors, and evidence.
        """
        return {
            "species": self.species,
            "score": round(self.score, 3),
            "light_score": round(self.light_score, 3),
            "water_score": round(self.water_score, 3),
            "soil_score": round(self.soil_score, 3),
            "heat_score": round(self.heat_score, 3),
            "space_score": round(self.space_score, 3),
            "limiting_factors": list(self.limiting_factors),
            "evidence": self.evidence.to_dict(),
        }


def _profile(
    name: str,
    common: str,
    group: SpeciesGroup,
    *,
    light: int,
    drought: int,
    water: float,
    soil: float,
    height: float,
    crown: float,
    native: bool,
    salt: int = 2,
    heat: int = 3,
    flood: int = 2,
    allergen: int = 2,
    bvoc: int = 2,
) -> SpeciesProfile:
    """Build a species profile with the shared source note.

    Parameters
    ----------
    name : str
        Scientific name.
    common : str
        Common name.
    group : str
        Species group.
    light, drought, salt, heat, flood, allergen, bvoc : int
        Trait scores from 1 to 5.
    water : float
        Relative water use.
    soil : float
        Minimum soil volume.
    height, crown : float
        Mature height and crown width.
    native : bool
        Native flag.

    Returns
    -------
    SpeciesProfile
        The profile.
    """
    return SpeciesProfile(
        name=name,
        common_name=common,
        group=group,
        light_demand=light,
        drought_tolerance=drought,
        water_use=water,
        min_soil_volume_m3=soil,
        mature_height_m=height,
        mature_crown_width_m=crown,
        native=native,
        salt_tolerance=salt,
        heat_tolerance=heat,
        flood_tolerance=flood,
        allergen_risk=allergen,
        bvoc_risk=bvoc,
        source="Transparent trait prior for Vancouver/Pacific Northwest screening",
        confidence="low-to-moderate; expert prior",
    )


PROFILES: tuple[SpeciesProfile, ...] = (
    _profile(
        "Acer macrophyllum",
        "Bigleaf maple",
        "deciduous",
        light=3,
        drought=2,
        water=1.2,
        soil=8.0,
        height=24.0,
        crown=16.0,
        native=True,
        salt=1,
        heat=2,
        flood=4,
        allergen=3,
    ),
    _profile(
        "Thuja plicata",
        "Western red cedar",
        "conifer",
        light=2,
        drought=2,
        water=1.0,
        soil=6.0,
        height=45.0,
        crown=9.0,
        native=True,
        salt=2,
        heat=2,
        flood=4,
        allergen=3,
    ),
    _profile(
        "Pseudotsuga menziesii",
        "Douglas-fir",
        "conifer",
        light=4,
        drought=4,
        water=0.8,
        soil=10.0,
        height=60.0,
        crown=10.0,
        native=True,
        salt=1,
        heat=3,
        flood=1,
        allergen=3,
    ),
    _profile(
        "Tsuga heterophylla",
        "Western hemlock",
        "conifer",
        light=2,
        drought=2,
        water=1.1,
        soil=8.0,
        height=55.0,
        crown=8.0,
        native=True,
        salt=1,
        heat=1,
        flood=2,
    ),
    _profile(
        "Quercus rubra",
        "Red oak",
        "deciduous",
        light=4,
        drought=4,
        water=0.7,
        soil=8.0,
        height=25.0,
        crown=18.0,
        native=False,
        salt=2,
        heat=4,
        flood=2,
    ),
    _profile(
        "Acer rubrum",
        "Red maple",
        "deciduous",
        light=3,
        drought=3,
        water=1.0,
        soil=6.0,
        height=20.0,
        crown=12.0,
        native=False,
        salt=2,
        heat=3,
        flood=3,
    ),
    _profile(
        "Prunus serrulata",
        "Japanese cherry",
        "deciduous",
        light=4,
        drought=2,
        water=1.0,
        soil=5.0,
        height=12.0,
        crown=9.0,
        native=False,
        salt=2,
        heat=2,
        flood=2,
        allergen=3,
    ),
    _profile(
        "Betula papyrifera",
        "Paper birch",
        "deciduous",
        light=4,
        drought=2,
        water=1.1,
        soil=5.0,
        height=18.0,
        crown=9.0,
        native=True,
        salt=1,
        heat=2,
        flood=2,
        allergen=4,
    ),
    _profile(
        "Gleditsia triacanthos",
        "Honey locust",
        "deciduous",
        light=5,
        drought=4,
        water=0.6,
        soil=5.0,
        height=18.0,
        crown=12.0,
        native=False,
        salt=4,
        heat=4,
        flood=2,
    ),
    _profile(
        "Liquidambar styraciflua",
        "Sweetgum",
        "deciduous",
        light=4,
        drought=3,
        water=0.9,
        soil=7.0,
        height=20.0,
        crown=11.0,
        native=False,
        salt=2,
        heat=3,
        flood=3,
    ),
    _profile(
        "Tilia cordata",
        "Littleleaf linden",
        "deciduous",
        light=3,
        drought=3,
        water=0.9,
        soil=7.0,
        height=18.0,
        crown=10.0,
        native=False,
        salt=2,
        heat=3,
        flood=2,
    ),
    _profile(
        "Pyrus calleryana",
        "Callery pear",
        "deciduous",
        light=5,
        drought=4,
        water=0.7,
        soil=4.0,
        height=12.0,
        crown=8.0,
        native=False,
        salt=3,
        heat=4,
        flood=2,
        allergen=3,
    ),
)


@lru_cache(maxsize=1)
def all_profiles() -> tuple[SpeciesProfile, ...]:
    """Return the built-in species profiles.

    Returns
    -------
    tuple of SpeciesProfile
        Profiles in table order.
    """
    return PROFILES


@lru_cache(maxsize=1024)
def profile_for_species(name: str) -> SpeciesProfile:
    """Resolve a species name to a profile.

    Parameters
    ----------
    name : str
        Scientific name, common name, or group label.

    Returns
    -------
    SpeciesProfile
        Exact match, then a genus or group fallback.
    """
    text = name.strip().lower()
    for profile in PROFILES:
        if text in {profile.name.lower(), profile.common_name.lower()}:
            return profile
    genus = text.split()[0] if text else ""
    for profile in PROFILES:
        if genus and profile.name.lower().startswith(genus + " "):
            return profile
    group = species_group(name)
    return _group_profile(group)


def site_fit(
    profile: SpeciesProfile,
    *,
    sun_fraction: float,
    soil_volume_m3: float,
    water_availability: float = 0.5,
    heat_exposure: float = 0.5,
    space_available_m: float = 10.0,
) -> SpeciesFit:
    """Score a species against a site's light, water, soil, heat, and space.

    Parameters
    ----------
    profile : SpeciesProfile
        Species traits.
    sun_fraction : float
        Fraction of daylight the site is directly sunlit, from zero to one.
    soil_volume_m3 : float
        Available soil volume per tree.
    water_availability : float
        Relative water availability from zero to one.
    heat_exposure : float
        Relative heat exposure from zero to one.
    space_available_m : float
        Available growing space in metres.

    Returns
    -------
    SpeciesFit
        Weighted score and limiting factors.
    """
    sun = _clamp(sun_fraction, 0.0, 1.0)
    preferred_sun = 0.15 + 0.15 * (profile.light_demand - 1)
    light_score = _clamp(1.0 - abs(sun - preferred_sun) / 0.80, 0.0, 1.0)
    water_need = profile.water_use * (0.55 + 0.45 * sun)
    water_score = _clamp(
        1.0 - max(0.0, water_need - water_availability) / max(water_need, 0.01), 0.0, 1.0
    )
    soil_score = _clamp(soil_volume_m3 / max(profile.min_soil_volume_m3, 0.1), 0.0, 1.0)
    heat_score = _clamp(1.0 - max(0.0, heat_exposure - profile.heat_tolerance / 5.0), 0.0, 1.0)
    space_score = _clamp(space_available_m / max(profile.mature_crown_width_m, 0.1), 0.0, 1.0)
    score = (
        0.35 * light_score
        + 0.25 * water_score
        + 0.20 * soil_score
        + 0.10 * heat_score
        + 0.10 * space_score
    )
    components = {
        "light": light_score,
        "water": water_score,
        "soil volume": soil_score,
        "heat": heat_score,
        "space": space_score,
    }
    limiting = tuple(
        factor
        for factor, value in sorted(components.items(), key=lambda item: item[1])
        if value < 0.6
    )
    return SpeciesFit(
        species=profile.name,
        score=_clamp(score, 0.0, 1.0),
        light_score=light_score,
        water_score=water_score,
        soil_score=soil_score,
        heat_score=heat_score,
        space_score=space_score,
        limiting_factors=limiting,
        evidence=FIT_EVIDENCE,
    )


def rank_species(
    names: tuple[str, ...],
    *,
    sun_fraction: float,
    soil_volume_m3: float,
    water_availability: float = 0.5,
    heat_exposure: float = 0.5,
    space_available_m: float = 10.0,
) -> tuple[SpeciesFit, ...]:
    """Rank a set of species by site fit.

    Parameters
    ----------
    names : tuple of str
        Species names.
    sun_fraction : float
        Fraction of daylight the site is sunlit.
    soil_volume_m3 : float
        Available soil volume.
    water_availability : float
        Relative water availability.
    heat_exposure : float
        Relative heat exposure.
    space_available_m : float
        Available growing space.

    Returns
    -------
    tuple of SpeciesFit
        Fits sorted from highest to lowest score.
    """
    fits = [
        site_fit(
            profile_for_species(name),
            sun_fraction=sun_fraction,
            soil_volume_m3=soil_volume_m3,
            water_availability=water_availability,
            heat_exposure=heat_exposure,
            space_available_m=space_available_m,
        )
        for name in names
    ]
    return tuple(sorted(fits, key=lambda item: item.score, reverse=True))


def _group_profile(group: SpeciesGroup) -> SpeciesProfile:
    """Return a fallback profile for a species group.

    Parameters
    ----------
    group : str
        Species group.

    Returns
    -------
    SpeciesProfile
        Group fallback.
    """
    if group == "conifer":
        return _profile(
            "conifer group",
            "Conifer (unknown species)",
            "conifer",
            light=3,
            drought=3,
            water=0.9,
            soil=7.0,
            height=35.0,
            crown=8.0,
            native=False,
        )
    if group == "deciduous":
        return _profile(
            "deciduous group",
            "Deciduous (unknown species)",
            "deciduous",
            light=3,
            drought=3,
            water=1.0,
            soil=6.0,
            height=18.0,
            crown=10.0,
            native=False,
        )
    return _profile(
        "unknown group",
        "Unknown species",
        "unknown",
        light=3,
        drought=3,
        water=1.0,
        soil=6.0,
        height=15.0,
        crown=8.0,
        native=False,
    )


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp a value to an interval.

    Parameters
    ----------
    value : float
        Input value.
    low : float
        Lower bound.
    high : float
        Upper bound.

    Returns
    -------
    float
        Clamped value.
    """
    if math.isnan(value):
        return low
    return max(low, min(high, value))
