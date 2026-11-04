"""Prior-driven two-stage bird demography.

The model is deliberately small: juveniles and adults, an annual matrix, a survival curve,
and a population growth rate. It is not a local mark-recapture estimate. Literature priors
and the habitat suitability index set the parameters; the output says so.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from fresh_urban_forest.evidence import Evidence, evidence
from fresh_urban_forest.habitat import BirdGuild

DEMOGRAPHY_EVIDENCE = evidence(
    "prior",
    "two-stage-bird-matrix",
    uncertainty=(
        "Survival and fecundity are literature/expert priors; no local mark-recapture or "
        "nest data are used. Lambda is a screening projection, not a forecast."
    ),
    source="Stage-structured matrix with prior ranges",
)


@dataclass(frozen=True, slots=True)
class DemographicProjection:
    """Projected bird population and lambda for one guild.

    Attributes
    ----------
    guild : BirdGuild
        Guild traits.
    habitat_score : float
        Habitat suitability used in the projection.
    lambda_value : float
        Annual population growth rate.
    population : tuple of tuple of float
        ``(year, juveniles, adults, total)`` rows.
    survival_curve : tuple of float
        Adult survival probability by year.
    stable_adult_fraction : float
        Stable-stage adult fraction.
    sensitivity : mapping of str to float
        Numerical sensitivity of lambda to survival and fecundity.
    prior_range : tuple of float
        Lambda at low and high prior scales.
    evidence : Evidence
        Method and tier.
    """

    guild: BirdGuild
    habitat_score: float
    lambda_value: float
    population: tuple[tuple[float, float, float, float], ...]
    survival_curve: tuple[float, ...]
    stable_adult_fraction: float
    sensitivity: Mapping[str, float]
    prior_range: tuple[float, float]
    evidence: Evidence

    def to_dict(self) -> dict[str, object]:
        """Convert the projection to JSON-safe values.

        Returns
        -------
        dict
            Lambda, population, survival curve, sensitivity, and evidence.
        """
        return {
            "guild": self.guild.to_dict(),
            "habitat_score": round(self.habitat_score, 4),
            "lambda": round(self.lambda_value, 4),
            "population": [
                {
                    "year": int(row[0]),
                    "juveniles": round(row[1], 2),
                    "adults": round(row[2], 2),
                    "total": round(row[3], 2),
                }
                for row in self.population
            ],
            "survival_curve": [round(value, 4) for value in self.survival_curve],
            "stable_adult_fraction": round(self.stable_adult_fraction, 4),
            "sensitivity": {key: round(value, 4) for key, value in self.sensitivity.items()},
            "prior_range": [round(value, 4) for value in self.prior_range],
            "evidence": self.evidence.to_dict(),
        }


def project_demography(
    guild: BirdGuild,
    habitat_score: float,
    *,
    years: int = 25,
    initial_juveniles: float = 20.0,
    initial_adults: float = 40.0,
) -> DemographicProjection:
    """Project a two-stage bird population under a habitat score.

    Parameters
    ----------
    guild : BirdGuild
        Guild survival and fecundity priors.
    habitat_score : float
        Suitability from zero to one.
    years : int
        Projection horizon.
    initial_juveniles : float
        Initial juvenile population.
    initial_adults : float
        Initial adult population.

    Returns
    -------
    DemographicProjection
        Lambda, annual population, survival curve, and sensitivity.
    """
    score = max(0.0, min(1.0, habitat_score))
    base = _parameters(guild, score, 1.0)
    low = _parameters(guild, score, 0.85)
    high = _parameters(guild, score, 1.15)
    lambda_value = _lambda(*base)
    prior_range = (_lambda(*low), _lambda(*high))
    juveniles = max(0.0, initial_juveniles)
    adults = max(0.0, initial_adults)
    population: list[tuple[float, float, float, float]] = [
        (0.0, juveniles, adults, juveniles + adults)
    ]
    survival_curve: list[float] = [1.0]
    fecundity, juvenile_survival, adult_survival = base
    for year in range(1, max(0, years) + 1):
        next_juveniles = fecundity * adults
        next_adults = juvenile_survival * juveniles + adult_survival * adults
        juveniles, adults = next_juveniles, next_adults
        population.append((float(year), juveniles, adults, juveniles + adults))
        survival_curve.append(adult_survival**year)
    stable_adult_fraction = _stable_adult_fraction(*base)
    sensitivity = _sensitivity(guild, score)
    return DemographicProjection(
        guild=guild,
        habitat_score=score,
        lambda_value=lambda_value,
        population=tuple(population),
        survival_curve=tuple(survival_curve),
        stable_adult_fraction=stable_adult_fraction,
        sensitivity=sensitivity,
        prior_range=prior_range,
        evidence=DEMOGRAPHY_EVIDENCE,
    )


def _parameters(guild: BirdGuild, score: float, scale: float) -> tuple[float, float, float]:
    """Return fecundity, juvenile survival, and adult survival."""
    fecundity = guild.fecundity * (0.45 + 0.55 * score) * scale
    juvenile = _clamp(guild.survival_juvenile * (0.80 + 0.20 * score) * scale, 0.02, 0.95)
    adult = _clamp(guild.survival_adult * (0.85 + 0.15 * score) * scale, 0.05, 0.98)
    return (fecundity, juvenile, adult)


def _lambda(fecundity: float, juvenile_survival: float, adult_survival: float) -> float:
    """Return the dominant eigenvalue of the two-stage matrix."""
    discriminant = adult_survival**2 + 4.0 * juvenile_survival * fecundity
    return float((adult_survival + math.sqrt(max(discriminant, 0.0))) / 2.0)


def _stable_adult_fraction(
    fecundity: float,
    juvenile_survival: float,
    adult_survival: float,
) -> float:
    """Return the stable-stage adult fraction."""
    lam = _lambda(fecundity, juvenile_survival, adult_survival)
    if fecundity <= 0.0:
        return 1.0
    juveniles = fecundity / max(lam, 1e-9) * 1.0
    adults = 1.0
    return float(adults / max(adults + juveniles, 1e-9))


def _sensitivity(guild: BirdGuild, score: float) -> Mapping[str, float]:
    """Numerically estimate lambda sensitivity to each prior parameter."""
    fecundity, juvenile, adult = _parameters(guild, score, 1.0)
    base = _lambda(fecundity, juvenile, adult)
    step = 0.01
    return {
        "fecundity": (_lambda(fecundity + step, juvenile, adult) - base) / step,
        "juvenile_survival": (_lambda(fecundity, juvenile + step, adult) - base) / step,
        "adult_survival": (_lambda(fecundity, juvenile, adult + step) - base) / step,
    }


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp a value to an interval."""
    return max(low, min(high, value))
