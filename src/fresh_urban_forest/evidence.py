"""Evidence tiers and provenance labels for modelled outputs.

The prototype mixes measurements, deterministic geometry, local fits, scenario projections,
and literature priors. A number without its tier is misleading, so every new light,
species, water, and growth output carries an :class:`Evidence` record.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EvidenceTier = Literal["measured", "physics", "calibrated", "scenario", "prior"]


@dataclass(frozen=True, slots=True)
class Evidence:
    """The method, tier, and uncertainty behind one output.

    Parameters
    ----------
    tier : str
        One of ``measured``, ``physics``, ``calibrated``, ``scenario``, or ``prior``.
    method : str
        Short method name, such as ``noaa-solar-position``.
    uncertainty : str
        A plain-language statement of the main uncertainty.
    source : str
        Source or model note, when one exists.
    """

    tier: EvidenceTier
    method: str
    uncertainty: str = ""
    source: str = ""

    def to_dict(self) -> dict[str, str]:
        """Convert the record to a JSON-safe dictionary.

        Returns
        -------
        dict of str to str
            The tier, method, uncertainty, and source.
        """
        return {
            "tier": self.tier,
            "method": self.method,
            "uncertainty": self.uncertainty,
            "source": self.source,
        }


def evidence(
    tier: EvidenceTier,
    method: str,
    *,
    uncertainty: str = "",
    source: str = "",
) -> Evidence:
    """Build an evidence record.

    Parameters
    ----------
    tier : str
        Evidence tier.
    method : str
        Short method name.
    uncertainty : str
        Main uncertainty statement.
    source : str
        Source or note.

    Returns
    -------
    Evidence
        The evidence record.
    """
    return Evidence(tier=tier, method=method, uncertainty=uncertainty, source=source)
