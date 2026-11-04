"""Tests for the prior-driven two-stage bird demography."""

from __future__ import annotations

from fresh_urban_forest.demography import project_demography
from fresh_urban_forest.habitat import GUILDS


def test_projection_returns_lambda_and_survival_curve() -> None:
    """A projection has a positive lambda, a survival curve, and prior range."""
    projection = project_demography(GUILDS[0], 0.7, years=10)
    assert projection.lambda_value > 0.0
    assert len(projection.survival_curve) == 11
    assert projection.survival_curve[0] == 1.0
    assert projection.survival_curve[-1] <= projection.survival_curve[0]
    assert projection.prior_range[0] <= projection.lambda_value <= projection.prior_range[1]
    assert 0.0 <= projection.stable_adult_fraction <= 1.0
    assert set(projection.sensitivity) == {
        "fecundity",
        "juvenile_survival",
        "adult_survival",
    }
    assert "evidence" in projection.to_dict()


def test_better_habitat_does_not_reduce_lambda() -> None:
    """A higher habitat score increases or preserves the growth rate."""
    low = project_demography(GUILDS[1], 0.1, years=5)
    high = project_demography(GUILDS[1], 0.9, years=5)
    assert high.lambda_value >= low.lambda_value
    assert high.population[-1][3] >= low.population[-1][3]


def test_projection_labels_prior_evidence() -> None:
    """The demographic output is explicitly prior-driven."""
    projection = project_demography(GUILDS[2], 0.5, years=3)
    assert projection.evidence.tier == "prior"
    assert "not a forecast" in projection.evidence.uncertainty
