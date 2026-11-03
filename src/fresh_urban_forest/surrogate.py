"""A small ridge-regression surrogate for screening planting decisions.

The surrogate is an explicitly labelled screening aid. The Pareto archive always uses the
exact evaluator; the surrogate report exists to show how much information aggregate counts
and site conditions carry about the seven objectives.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import numpy as np

from fresh_urban_forest.evidence import Evidence, evidence
from fresh_urban_forest.optimize import OptimizationProblem, evaluate_solution

SURROGATE_EVIDENCE = evidence(
    "prior",
    "ridge-regression-surrogate",
    uncertainty="Aggregate-feature linear emulator; it does not replace the exact evaluator.",
    source="Design-of-experiments sample from the exact evaluator",
)


@dataclass(frozen=True, slots=True)
class SurrogateReport:
    """Validation metrics for one surrogate fit.

    Attributes
    ----------
    sample_count : int
        Total design samples.
    train_count : int
        Training samples.
    test_count : int
        Holdout samples.
    rmse : tuple of float
        Holdout RMSE per objective.
    r2 : tuple of float
        Holdout R2 per objective.
    feature_names : tuple of str
        Aggregate feature names.
    objective_names : tuple of str
        Objective names.
    evidence : Evidence
        Method and tier.
    """

    sample_count: int
    train_count: int
    test_count: int
    rmse: tuple[float, ...]
    r2: tuple[float, ...]
    feature_names: tuple[str, ...]
    objective_names: tuple[str, ...]
    evidence: Evidence

    def to_dict(self) -> dict[str, object]:
        """Convert the report to JSON-safe values.

        Returns
        -------
        dict
            Counts, errors, R2, and evidence.
        """
        return {
            "sample_count": self.sample_count,
            "train_count": self.train_count,
            "test_count": self.test_count,
            "rmse": [round(value, 6) for value in self.rmse],
            "r2": [round(value, 6) for value in self.r2],
            "feature_names": list(self.feature_names),
            "objective_names": list(self.objective_names),
            "evidence": self.evidence.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class SurrogateModel:
    """A fitted ridge surrogate.

    Attributes
    ----------
    report : SurrogateReport
        Validation report.
    coefficients : tuple of tuple of float
        Feature coefficients per objective.
    intercepts : tuple of float
        Intercepts per objective.
    means : tuple of float
        Feature means.
    scales : tuple of float
        Feature scales.
    """

    report: SurrogateReport
    coefficients: tuple[tuple[float, ...], ...]
    intercepts: tuple[float, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]

    def predict(
        self, problem: OptimizationProblem, decisions: tuple[int, ...]
    ) -> tuple[float, ...]:
        """Predict the objective vector for one decision.

        Parameters
        ----------
        problem : OptimizationProblem
            Problem definition.
        decisions : tuple of int
            Species index per site.

        Returns
        -------
        tuple of float
            Predicted objective values.
        """
        features = np.asarray(surrogate_features(problem, decisions), dtype=np.float64)
        normalised = (features - np.asarray(self.means)) / np.asarray(self.scales)
        return tuple(
            float(value)
            for value in (normalised @ np.asarray(self.coefficients) + np.asarray(self.intercepts))
        )

    def to_dict(self) -> dict[str, object]:
        """Convert the model to JSON-safe values.

        Returns
        -------
        dict
            Report and coefficient matrix.
        """
        return {
            "report": self.report.to_dict(),
            "intercepts": [round(value, 6) for value in self.intercepts],
            "coefficients": [[round(value, 6) for value in row] for row in self.coefficients],
        }


def surrogate_features(
    problem: OptimizationProblem, decisions: tuple[int, ...]
) -> tuple[float, ...]:
    """Build aggregate features for one decision.

    Parameters
    ----------
    problem : OptimizationProblem
        Problem definition.
    decisions : tuple of int
        Species index per site.

    Returns
    -------
    tuple of float
        Aggregate features.
    """
    vector = tuple(int(value) for value in decisions[: len(problem.sites)])
    if len(vector) < len(problem.sites):
        vector = vector + (0,) * (len(problem.sites) - len(vector))
    counts = [0.0] * len(problem.species)
    sun = 0.0
    heat = 0.0
    soil = 0.0
    base = 0.0
    selected = 0
    for index, option in enumerate(vector):
        if option <= 0:
            continue
        selected += 1
        counts[option - 1] += 1.0
        site = problem.sites[index]
        sun += site.sun_fraction
        heat += site.heat_weight
        soil += site.soil_volume_m3
        base += site.base_score
    denominator = max(selected, 1)
    return (
        float(selected),
        *counts,
        sun / denominator,
        heat / denominator,
        soil / denominator,
        base / denominator,
    )


def fit_surrogate(
    problem: OptimizationProblem,
    *,
    samples: int = 64,
    seed: int = 42,
) -> SurrogateModel:
    """Fit and validate a ridge surrogate on a random design.

    Parameters
    ----------
    problem : OptimizationProblem
        Problem definition.
    samples : int
        Number of design samples.
    seed : int
        Random seed.

    Returns
    -------
    SurrogateModel
        Fitted model and holdout report.
    """
    rng = random.Random(seed)
    assignments: list[tuple[int, ...]] = []
    for _ in range(max(8, samples)):
        assignments.append(
            tuple(
                0 if rng.random() > 0.35 else rng.randint(1, len(problem.species))
                for _ in problem.sites
            )
        )
    solutions = [evaluate_solution(problem, decisions) for decisions in assignments]
    features = np.asarray(
        [surrogate_features(problem, decisions) for decisions in assignments],
        dtype=np.float64,
    )
    targets = np.asarray([solution.objectives for solution in solutions], dtype=np.float64)
    means = features.mean(axis=0)
    scales = features.std(axis=0)
    scales = np.where(scales <= 1e-12, 1.0, scales)
    normalised = (features - means) / scales
    split = max(1, int(len(assignments) * 0.8))
    train_x = normalised[:split]
    test_x = normalised[split:] if split < len(assignments) else normalised[:split]
    train_y = targets[:split]
    test_y = targets[split:] if split < len(assignments) else targets[:split]
    train_x = np.column_stack([np.ones(len(train_x)), train_x])
    test_x = np.column_stack([np.ones(len(test_x)), test_x])
    ridge = 1e-4 * np.eye(train_x.shape[1])
    coefficients = np.linalg.pinv(train_x.T @ train_x + ridge) @ train_x.T @ train_y
    predictions = test_x @ coefficients
    residuals = test_y - predictions
    rmse = np.sqrt(np.mean(residuals**2, axis=0))
    variance = np.var(test_y, axis=0)
    r2 = np.where(variance <= 1e-12, 0.0, 1.0 - np.var(residuals, axis=0) / variance)
    feature_names = (
        "selected_count",
        *[f"count:{option.name}" for option in problem.species],
        "mean_sun",
        "mean_heat",
        "mean_soil",
        "mean_base_score",
    )
    report = SurrogateReport(
        sample_count=len(assignments),
        train_count=len(train_x),
        test_count=len(test_x),
        rmse=tuple(float(value) for value in rmse),
        r2=tuple(float(value) for value in r2),
        feature_names=feature_names,
        objective_names=tuple(objective.name for objective in problem.objectives),
        evidence=SURROGATE_EVIDENCE,
    )
    return SurrogateModel(
        report=report,
        coefficients=tuple(tuple(float(value) for value in row) for row in coefficients[1:]),
        intercepts=tuple(float(value) for value in coefficients[0]),
        means=tuple(float(value) for value in means),
        scales=tuple(float(value) for value in scales),
    )


def _finite(value: float, default: float = 0.0) -> float:
    """Return a finite value or a default."""
    return value if math.isfinite(value) else default
