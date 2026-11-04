"""Tests for the screening surrogate."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from fresh_urban_forest.optimize import OptimizationProblem, build_problem
from fresh_urban_forest.surrogate import fit_surrogate, surrogate_features
from tests.fixtures import make_dataset


def _problem(tmp_path: Path) -> OptimizationProblem:
    """Build a small problem for surrogate tests."""
    return build_problem(
        make_dataset(tmp_path),
        site_count=8,
        species=("Acer rubrum", "Thuja plicata", "Quercus rubra"),
        horizon=5,
    )


def test_features_are_finite_and_shaped(tmp_path: Path) -> None:
    """Aggregate features have one count per species and four site means."""
    problem = _problem(tmp_path)
    features = surrogate_features(problem, (1, 2, 0, 0, 0, 0, 0, 0))
    assert len(features) == 1 + len(problem.species) + 4
    assert all(np.isfinite(value) for value in features)


def test_surrogate_reports_holdout_error(tmp_path: Path) -> None:
    """The surrogate fit reports finite RMSE and R2 values."""
    problem = _problem(tmp_path)
    model = fit_surrogate(problem, samples=32, seed=3)
    report = model.report
    assert report.sample_count >= 8
    assert report.train_count > 0
    assert report.test_count > 0
    assert len(report.rmse) == len(problem.objectives)
    assert all(np.isfinite(value) for value in report.rmse)
    assert all(np.isfinite(value) for value in report.r2)
    prediction = model.predict(problem, (1, 0, 0, 0, 0, 0, 0, 0))
    assert len(prediction) == len(problem.objectives)
    assert "report" in model.to_dict()
