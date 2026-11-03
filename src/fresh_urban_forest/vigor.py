"""Light, water, heat, and soil modifiers for tree growth and vigour.

The response model is a transparent multiplier stack, not a calibrated process model. It
makes the trade-off visible: a shaded site reduces light but can also reduce water demand,
while an open street tree gets more light and often more drought stress.
"""

from __future__ import annotations

from dataclasses import dataclass

from fresh_urban_forest.allometry import (
    annual_dbh_increment_cm,
    estimate_crown_width_m,
    estimate_height_m,
)
from fresh_urban_forest.evidence import Evidence, evidence
from fresh_urban_forest.species import SpeciesProfile
from fresh_urban_forest.water import WaterBalance

VIGOR_EVIDENCE = evidence(
    "scenario",
    "light-water-heat-soil-modifier",
    uncertainty=(
        "Multiplier stack with expert priors; not a calibrated local growth model and not "
        "a drought-mortality model."
    ),
    source="Transparent growth-response model; local repeat measurements are still required.",
)


@dataclass(frozen=True, slots=True)
class GrowthResponse:
    """The multiplicative growth response at one site.

    Attributes
    ----------
    light_modifier : float
        Light multiplier.
    water_modifier : float
        Water multiplier.
    heat_modifier : float
        Heat multiplier.
    soil_modifier : float
        Soil-volume multiplier.
    competition_modifier : float
        Competition multiplier.
    combined : float
        Product of the modifiers.
    vigor_score : float
        Combined response clamped to zero to one.
    stress_days : int
        Water-stress days from the balance.
    evidence : Evidence
        Method and tier.
    """

    light_modifier: float
    water_modifier: float
    heat_modifier: float
    soil_modifier: float
    competition_modifier: float
    combined: float
    vigor_score: float
    stress_days: int
    evidence: Evidence

    def to_dict(self) -> dict[str, object]:
        """Convert the response to a JSON-safe dictionary.

        Returns
        -------
        dict
            Modifiers, vigour, stress, and evidence.
        """
        return {
            "light_modifier": round(self.light_modifier, 3),
            "water_modifier": round(self.water_modifier, 3),
            "heat_modifier": round(self.heat_modifier, 3),
            "soil_modifier": round(self.soil_modifier, 3),
            "competition_modifier": round(self.competition_modifier, 3),
            "combined": round(self.combined, 3),
            "vigor_score": round(self.vigor_score, 3),
            "stress_days": self.stress_days,
            "evidence": self.evidence.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class GrowthPoint:
    """One year in a species growth projection.

    Attributes
    ----------
    year : int
        Years from the start.
    dbh_cm : float
        Diameter at breast height.
    height_m : float
        Estimated height.
    crown_width_m : float
        Estimated crown width.
    vigor_score : float
        Vigour at that year.
    """

    year: int
    dbh_cm: float
    height_m: float
    crown_width_m: float
    vigor_score: float

    def to_dict(self) -> dict[str, object]:
        """Convert the point to a JSON-safe dictionary.

        Returns
        -------
        dict
            Year and size values.
        """
        return {
            "year": self.year,
            "dbh_cm": round(self.dbh_cm, 2),
            "height_m": round(self.height_m, 2),
            "crown_width_m": round(self.crown_width_m, 2),
            "vigor_score": round(self.vigor_score, 3),
        }


@dataclass(frozen=True, slots=True)
class GrowthProjection:
    """A species growth projection under one site response.

    Attributes
    ----------
    species : str
        Species name.
    points : tuple of GrowthPoint
        Annual points including year zero.
    response : GrowthResponse
        Site response used for the projection.
    evidence : Evidence
        Method and tier.
    """

    species: str
    points: tuple[GrowthPoint, ...]
    response: GrowthResponse
    evidence: Evidence

    def to_dict(self) -> dict[str, object]:
        """Convert the projection to a JSON-safe dictionary.

        Returns
        -------
        dict
            Species, annual points, response, and evidence.
        """
        return {
            "species": self.species,
            "points": [point.to_dict() for point in self.points],
            "response": self.response.to_dict(),
            "evidence": self.evidence.to_dict(),
        }


def growth_response(
    profile: SpeciesProfile,
    *,
    sun_fraction: float,
    water: WaterBalance,
    soil_volume_m3: float,
    heat_exposure: float = 0.5,
    competition: float = 1.0,
) -> GrowthResponse:
    """Combine light, water, heat, soil, and competition into a growth response.

    Parameters
    ----------
    profile : SpeciesProfile
        Species traits.
    sun_fraction : float
        Fraction of daylight the site is sunlit.
    water : WaterBalance
        Annual water balance.
    soil_volume_m3 : float
        Available soil volume.
    heat_exposure : float
        Relative heat exposure from zero to one.
    competition : float
        Competition multiplier where one is open-grown.

    Returns
    -------
    GrowthResponse
        Modifiers, combined response, vigour, and stress.
    """
    sun = _clamp(sun_fraction, 0.0, 1.0)
    preferred = 0.15 + 0.15 * (profile.light_demand - 1)
    light = _clamp(1.0 - 0.55 * abs(sun - preferred) / 0.80, 0.30, 1.05)
    water_modifier = _clamp(1.0 - 0.65 * (water.stress_days / 365.0), 0.25, 1.0)
    heat = _clamp(
        1.0 - 0.30 * max(0.0, heat_exposure - profile.heat_tolerance / 5.0),
        0.55,
        1.0,
    )
    soil = _clamp(
        0.55 + 0.45 * min(soil_volume_m3 / max(profile.min_soil_volume_m3, 0.1), 1.0),
        0.55,
        1.0,
    )
    competition_modifier = _clamp(competition, 0.3, 1.2)
    combined = _clamp(light * water_modifier * heat * soil * competition_modifier, 0.03, 1.2)
    return GrowthResponse(
        light_modifier=light,
        water_modifier=water_modifier,
        heat_modifier=heat,
        soil_modifier=soil,
        competition_modifier=competition_modifier,
        combined=combined,
        vigor_score=_clamp(combined, 0.0, 1.0),
        stress_days=water.stress_days,
        evidence=VIGOR_EVIDENCE,
    )


def project_species_growth(
    profile: SpeciesProfile,
    response: GrowthResponse,
    *,
    initial_dbh_cm: float,
    years: int,
) -> GrowthProjection:
    """Project DBH, height, crown, and vigour for a species.

    Parameters
    ----------
    profile : SpeciesProfile
        Species traits.
    response : GrowthResponse
        Site response.
    initial_dbh_cm : float
        Starting diameter.
    years : int
        Projection horizon.

    Returns
    -------
    GrowthProjection
        Annual points and evidence.
    """
    group = profile.group
    dbh = max(initial_dbh_cm, 1.0)
    points: list[GrowthPoint] = []
    for year in range(max(0, years) + 1):
        height = estimate_height_m(dbh, group)
        crown = estimate_crown_width_m(dbh, group)
        points.append(
            GrowthPoint(
                year=year,
                dbh_cm=dbh,
                height_m=height,
                crown_width_m=crown,
                vigor_score=response.vigor_score,
            )
        )
        if year < years:
            dbh += annual_dbh_increment_cm(
                dbh,
                group,
                competition=response.combined,
            )
    return GrowthProjection(
        species=profile.name,
        points=tuple(points),
        response=response,
        evidence=VIGOR_EVIDENCE,
    )


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp a value to an interval.

    Parameters
    ----------
    value : float
        Input.
    low : float
        Lower bound.
    high : float
        Upper bound.

    Returns
    -------
    float
        Clamped value.
    """
    return max(low, min(high, value))
