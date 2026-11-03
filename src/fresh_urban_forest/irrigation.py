"""Irrigation-policy comparison and cost per effective shade-hour.

The options are planning scenarios, not utility bills. Each one carries its water volume,
stress days, labour visits, annual cost, and the cost of the shade it supports.
"""

from __future__ import annotations

from dataclasses import dataclass

from fresh_urban_forest.evidence import Evidence, evidence
from fresh_urban_forest.species import SpeciesProfile
from fresh_urban_forest.water import (
    DEFAULT_ASSUMPTIONS,
    DEFAULT_CLIMATE,
    ClimateSeries,
    WaterAssumptions,
    WaterBalance,
    compare_water_policies,
)

IRRIGATION_EVIDENCE = evidence(
    "scenario",
    "irrigation-policy-cost",
    uncertainty=(
        "Water price, labour rate, and visit frequency are configurable assumptions, not "
        "a utility bill or a maintenance contract."
    ),
    source="Single-bucket water balance plus transparent cost assumptions",
)


@dataclass(frozen=True, slots=True)
class IrrigationOption:
    """One irrigation policy with its cost per shade-hour.

    Attributes
    ----------
    balance : WaterBalance
        Underlying water balance.
    shade_area_hours : float
        Effective shade area-hours supported by the tree.
    cost_per_shade_hour : float
        Annual cost divided by shade area-hours.
    recommendation : str
        Short ranking label.
    evidence : Evidence
        Method and tier.
    """

    balance: WaterBalance
    shade_area_hours: float
    cost_per_shade_hour: float
    recommendation: str
    evidence: Evidence

    def to_dict(self) -> dict[str, object]:
        """Convert the option to a JSON-safe dictionary.

        Returns
        -------
        dict
            Water balance, shade, cost per shade-hour, and evidence.
        """
        payload = self.balance.to_dict()
        payload.update(
            {
                "shade_area_hours": round(self.shade_area_hours, 1),
                "cost_per_shade_hour": round(self.cost_per_shade_hour, 4),
                "recommendation": self.recommendation,
                "evidence": self.evidence.to_dict(),
            }
        )
        return payload


def compare_irrigation(
    profile: SpeciesProfile,
    *,
    crown_area_m2: float,
    soil_volume_m3: float,
    sun_fraction: float,
    shade_area_hours: float,
    age_years: float = 10.0,
    climate: ClimateSeries = DEFAULT_CLIMATE,
    assumptions: WaterAssumptions = DEFAULT_ASSUMPTIONS,
) -> tuple[IrrigationOption, ...]:
    """Compare irrigation policies and rank them by cost and stress.

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
    shade_area_hours : float
        Effective shade area-hours supported by the tree.
    age_years : float
        Tree age.
    climate : ClimateSeries
        Monthly climate.
    assumptions : WaterAssumptions
        Economic and soil assumptions.

    Returns
    -------
    tuple of IrrigationOption
        Options sorted by recommendation rank and then annual cost.
    """
    balances = compare_water_policies(
        profile,
        crown_area_m2=crown_area_m2,
        soil_volume_m3=soil_volume_m3,
        sun_fraction=sun_fraction,
        age_years=age_years,
        climate=climate,
        assumptions=assumptions,
    )
    minimum_stress = min(balance.stress_days for balance in balances)
    options: list[IrrigationOption] = []
    for balance in balances:
        cost = balance.annual_cost_cad / max(shade_area_hours, 1.0)
        label = _recommendation(balance, minimum_stress)
        options.append(
            IrrigationOption(
                balance=balance,
                shade_area_hours=shade_area_hours,
                cost_per_shade_hour=cost,
                recommendation=label,
                evidence=IRRIGATION_EVIDENCE,
            )
        )
    rank = {"best balance": 0, "low cost": 1, "high stress": 2, "high cost": 3}
    return tuple(
        sorted(
            options,
            key=lambda item: (
                rank.get(item.recommendation, 9),
                item.balance.annual_cost_cad,
            ),
        )
    )


def _recommendation(balance: WaterBalance, minimum_stress: int) -> str:
    """Label one policy from its stress and cost.

    Parameters
    ----------
    balance : WaterBalance
        Policy balance.
    minimum_stress : int
        Lowest stress days among the compared policies.

    Returns
    -------
    str
        Recommendation label.
    """
    if balance.stress_days <= max(minimum_stress + 2, 5) and balance.annual_cost_cad <= 450.0:
        return "best balance"
    if balance.stress_days > minimum_stress + 20:
        return "high stress"
    if balance.annual_cost_cad > 450.0:
        return "high cost"
    return "low cost"
