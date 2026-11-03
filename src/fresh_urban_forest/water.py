"""Daily soil-water balance and irrigation-policy screening.

The model is a single bucket per tree: rainfall and irrigation fill it, evapotranspiration
draws it down, and excess drains as runoff. It is deliberately simple and transparent. The
default climate is an illustrative Vancouver monthly series, not a measured weather file.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from fresh_urban_forest.evidence import Evidence, evidence
from fresh_urban_forest.species import SpeciesProfile

IrrigationPolicyName = Literal["none", "establishment", "fixed", "moisture_trigger", "deficit"]
WATER_EVIDENCE = evidence(
    "prior",
    "single-bucket-water-balance",
    uncertainty=(
        "Illustrative monthly climate, one soil bucket per tree, and expert water-use "
        "coefficients; not a soil-moisture sensor or utility bill."
    ),
    source="FAO-56-style reference ET concept, simplified for screening",
)

DEFAULT_PRECIP_MM: tuple[float, ...] = (
    180.0,
    120.0,
    100.0,
    70.0,
    60.0,
    50.0,
    30.0,
    40.0,
    60.0,
    120.0,
    190.0,
    200.0,
)
DEFAULT_ET0_MM: tuple[float, ...] = (
    8.0,
    15.0,
    30.0,
    50.0,
    70.0,
    85.0,
    95.0,
    85.0,
    55.0,
    30.0,
    12.0,
    6.0,
)


@dataclass(frozen=True, slots=True)
class ClimateSeries:
    """A monthly precipitation and reference-evapotranspiration series.

    Attributes
    ----------
    label : str
        Human-readable climate label.
    precip_mm : tuple of float
        Monthly precipitation in millimetres, January to December.
    et0_mm : tuple of float
        Monthly reference evapotranspiration in millimetres.
    source : str
        Source note.
    """

    label: str
    precip_mm: tuple[float, ...]
    et0_mm: tuple[float, ...]
    source: str

    def __post_init__(self) -> None:
        """Validate the monthly series length.

        Raises
        ------
        ValueError
            When either series does not have twelve values.
        """
        if len(self.precip_mm) != 12 or len(self.et0_mm) != 12:
            raise ValueError("climate series needs twelve monthly values")


DEFAULT_CLIMATE = ClimateSeries(
    label="Illustrative Vancouver monthly climate",
    precip_mm=DEFAULT_PRECIP_MM,
    et0_mm=DEFAULT_ET0_MM,
    source="Illustrative monthly climatology; replace with a local TMY or weather file.",
)


@dataclass(frozen=True, slots=True)
class WaterAssumptions:
    """Economic and soil assumptions for the water balance.

    Attributes
    ----------
    water_price_cad_per_m3 : float
        Municipal water price.
    labour_cad_per_visit : float
        Cost of one irrigation visit.
    available_water_fraction : float
        Plant-available water per cubic metre of soil, as a fraction.
    initial_fill : float
        Initial soil-water fraction of capacity.
    stress_fraction : float
        Soil-water fraction below which a day counts as stressed.
    """

    water_price_cad_per_m3: float = 3.50
    labour_cad_per_visit: float = 35.0
    available_water_fraction: float = 0.15
    initial_fill: float = 0.65
    stress_fraction: float = 0.35


DEFAULT_ASSUMPTIONS = WaterAssumptions()


@dataclass(frozen=True, slots=True)
class WaterBalance:
    """Annual water balance and cost for one tree and one policy.

    Attributes
    ----------
    policy : str
        Irrigation policy.
    annual_precip_l : float
        Rainfall captured by the crown.
    annual_et_l : float
        Evapotranspiration demand.
    irrigation_l : float
        Irrigation applied.
    runoff_l : float
        Water lost to overflow.
    stress_days : int
        Days below the stress threshold.
    min_soil_fraction : float
        Minimum soil-water fraction.
    mean_soil_fraction : float
        Mean soil-water fraction.
    water_cost_cad : float
        Water cost.
    labour_cost_cad : float
        Labour cost.
    annual_cost_cad : float
        Total annual cost.
    visits : int
        Irrigation visits per year.
    evidence : Evidence
        Method and tier.
    """

    policy: str
    annual_precip_l: float
    annual_et_l: float
    irrigation_l: float
    runoff_l: float
    stress_days: int
    min_soil_fraction: float
    mean_soil_fraction: float
    water_cost_cad: float
    labour_cost_cad: float
    annual_cost_cad: float
    visits: int
    evidence: Evidence

    def to_dict(self) -> dict[str, object]:
        """Convert the balance to a JSON-safe dictionary.

        Returns
        -------
        dict
            Water volumes, stress, cost, and evidence.
        """
        return {
            "policy": self.policy,
            "annual_precip_l": round(self.annual_precip_l, 1),
            "annual_et_l": round(self.annual_et_l, 1),
            "irrigation_l": round(self.irrigation_l, 1),
            "runoff_l": round(self.runoff_l, 1),
            "stress_days": self.stress_days,
            "min_soil_fraction": round(self.min_soil_fraction, 3),
            "mean_soil_fraction": round(self.mean_soil_fraction, 3),
            "water_cost_cad": round(self.water_cost_cad, 2),
            "labour_cost_cad": round(self.labour_cost_cad, 2),
            "annual_cost_cad": round(self.annual_cost_cad, 2),
            "visits": self.visits,
            "evidence": self.evidence.to_dict(),
        }


def simulate_water_balance(
    profile: SpeciesProfile,
    *,
    crown_area_m2: float,
    soil_volume_m3: float,
    sun_fraction: float,
    policy: IrrigationPolicyName = "none",
    climate: ClimateSeries = DEFAULT_CLIMATE,
    age_years: float = 10.0,
    assumptions: WaterAssumptions = DEFAULT_ASSUMPTIONS,
) -> WaterBalance:
    """Simulate one year of soil water and irrigation for one tree.

    Parameters
    ----------
    profile : SpeciesProfile
        Species water-use traits.
    crown_area_m2 : float
        Projected crown area.
    soil_volume_m3 : float
        Available soil volume.
    sun_fraction : float
        Fraction of daylight the site is sunlit.
    policy : str
        Irrigation policy.
    climate : ClimateSeries
        Monthly climate.
    age_years : float
        Tree age since planting.
    assumptions : WaterAssumptions
        Economic and soil assumptions.

    Returns
    -------
    WaterBalance
        Annual water balance and cost.
    """
    area = max(crown_area_m2, 1.0)
    soil_capacity = max(
        soil_volume_m3 * 1000.0 * assumptions.available_water_fraction,
        25.0,
    )
    soil = soil_capacity * assumptions.initial_fill
    stress_days = 0
    irrigation_total = 0.0
    precip_total = 0.0
    et_total = 0.0
    runoff_total = 0.0
    minimum = soil / soil_capacity
    total = 0.0
    water_factor = profile.water_use * (0.55 + 0.45 * max(0.0, min(1.0, sun_fraction)))
    for month in range(12):
        days = 30.0
        daily_precip = climate.precip_mm[month] / days
        daily_et = climate.et0_mm[month] * water_factor * area / days
        for _ in range(int(days)):
            rain = daily_precip * area * 0.75
            soil += rain - daily_et
            precip_total += rain
            et_total += daily_et
            irrigation = _policy_water(
                policy,
                soil,
                soil_capacity,
                area,
                age_years,
            )
            if irrigation > 0.0:
                soil += irrigation
                irrigation_total += irrigation
            if soil > soil_capacity:
                runoff_total += soil - soil_capacity
                soil = soil_capacity
            if soil < 0.0:
                soil = 0.0
            if soil / soil_capacity < assumptions.stress_fraction:
                stress_days += 1
            minimum = min(minimum, soil / soil_capacity)
            total += soil / soil_capacity
    visits = _visits(policy, age_years)
    water_cost = irrigation_total / 1000.0 * assumptions.water_price_cad_per_m3
    labour_cost = visits * assumptions.labour_cad_per_visit
    return WaterBalance(
        policy=policy,
        annual_precip_l=precip_total,
        annual_et_l=et_total,
        irrigation_l=irrigation_total,
        runoff_l=runoff_total,
        stress_days=stress_days,
        min_soil_fraction=minimum,
        mean_soil_fraction=total / 365.0,
        water_cost_cad=water_cost,
        labour_cost_cad=labour_cost,
        annual_cost_cad=water_cost + labour_cost,
        visits=visits,
        evidence=WATER_EVIDENCE,
    )


def compare_water_policies(
    profile: SpeciesProfile,
    *,
    crown_area_m2: float,
    soil_volume_m3: float,
    sun_fraction: float,
    age_years: float = 10.0,
    climate: ClimateSeries = DEFAULT_CLIMATE,
    assumptions: WaterAssumptions = DEFAULT_ASSUMPTIONS,
) -> tuple[WaterBalance, ...]:
    """Compare the standard irrigation policies.

    Parameters
    ----------
    profile : SpeciesProfile
        Species traits.
    crown_area_m2 : float
        Projected crown area.
    soil_volume_m3 : float
        Available soil volume.
    sun_fraction : float
        Sunlit fraction.
    age_years : float
        Tree age.
    climate : ClimateSeries
        Monthly climate.
    assumptions : WaterAssumptions
        Economic and soil assumptions.

    Returns
    -------
    tuple of WaterBalance
        One balance per policy.
    """
    policies: tuple[IrrigationPolicyName, ...] = (
        "none",
        "establishment",
        "fixed",
        "moisture_trigger",
        "deficit",
    )
    return tuple(
        simulate_water_balance(
            profile,
            crown_area_m2=crown_area_m2,
            soil_volume_m3=soil_volume_m3,
            sun_fraction=sun_fraction,
            policy=policy,
            climate=climate,
            age_years=age_years,
            assumptions=assumptions,
        )
        for policy in policies
    )


def _policy_water(
    policy: IrrigationPolicyName,
    soil: float,
    capacity: float,
    area: float,
    age_years: float,
) -> float:
    """Return irrigation litres for one day under a policy.

    Parameters
    ----------
    policy : str
        Irrigation policy.
    soil : float
        Current soil water in litres.
    capacity : float
        Soil-water capacity in litres.
    area : float
        Crown area in square metres.
    age_years : float
        Tree age.

    Returns
    -------
    float
        Irrigation litres.
    """
    if policy == "none":
        return 0.0
    if policy == "establishment":
        if age_years > 3.0:
            return 0.0
        return max(0.0, capacity * 0.85 - soil) if soil < capacity * 0.55 else 0.0
    if policy == "fixed":
        return area * 40.0 / 30.0
    if policy == "moisture_trigger":
        return max(0.0, capacity * 0.85 - soil) if soil < capacity * 0.50 else 0.0
    if policy == "deficit":
        return max(0.0, capacity * 0.55 - soil) if soil < capacity * 0.35 else 0.0


def _visits(policy: IrrigationPolicyName, age_years: float) -> int:
    """Return annual irrigation visits for a policy.

    Parameters
    ----------
    policy : str
        Irrigation policy.
    age_years : float
        Tree age.

    Returns
    -------
    int
        Visits per year.
    """
    if policy == "none":
        return 0
    if policy == "establishment":
        return 12 if age_years <= 3.0 else 0
    if policy == "fixed":
        return 30
    if policy == "moisture_trigger":
        return 12
    if policy == "deficit":
        return 6


def water_summary(balance: WaterBalance) -> dict[str, object]:
    """Return a compact water summary.

    Parameters
    ----------
    balance : WaterBalance
        Water balance to summarise.

    Returns
    -------
    dict
        JSON-safe balance.
    """
    return balance.to_dict()


def _finite(value: float, default: float = 0.0) -> float:
    """Return a finite float or a default.

    Parameters
    ----------
    value : float
        Input.
    default : float
        Fallback.

    Returns
    -------
    float
        Finite value.
    """
    return value if math.isfinite(value) else default
