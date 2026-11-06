"""Transparent conifer/deciduous classification and QA metrics.

The available labels are public tree inventories, not field species audits. The baseline is
a small standardized logistic regression so coefficients, features, and failures remain
inspectable. It is a screening classifier, not a species identification model.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize
from scipy.special import expit

Group = Literal["conifer", "deciduous"]
FEATURE_NAMES: tuple[str, ...] = (
    "height_m",
    "log_height",
    "crown_width_m",
    "height_crown_ratio",
)


@dataclass(frozen=True, slots=True)
class LogisticModel:
    """A standardized binary logistic-regression model.

    Attributes
    ----------
    feature_names : tuple of str
        Feature order.
    means : numpy.ndarray
        Training means.
    scales : numpy.ndarray
        Training standard deviations, with zero replaced by one.
    coefficients : numpy.ndarray
        Standardized coefficients.
    intercept : float
        Intercept.
    threshold : float
        Probability threshold for the positive (conifer) class.
    """

    feature_names: tuple[str, ...]
    means: NDArray[np.float64]
    scales: NDArray[np.float64]
    coefficients: NDArray[np.float64]
    intercept: float
    threshold: float = 0.5

    def predict_proba(self, features: NDArray[np.float64]) -> NDArray[np.float64]:
        """Return conifer probabilities.

        Parameters
        ----------
        features : numpy.ndarray
            Feature matrix with columns in ``feature_names`` order.

        Returns
        -------
        numpy.ndarray
            Probability of conifer for each row.
        """
        matrix = np.asarray(features, dtype=np.float64)
        if matrix.ndim != 2 or matrix.shape[1] != len(self.feature_names):
            raise ValueError("features do not match the model feature count")
        standardized = (matrix - self.means) / self.scales
        return np.asarray(
            expit(standardized @ self.coefficients + self.intercept), dtype=np.float64
        )

    def predict(self, features: NDArray[np.float64]) -> NDArray[np.bool_]:
        """Return conifer predictions.

        Parameters
        ----------
        features : numpy.ndarray
            Feature matrix.

        Returns
        -------
        numpy.ndarray of bool
            ``True`` for conifer.
        """
        return self.predict_proba(features) >= self.threshold

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe model artifact.

        Returns
        -------
        dict
            Feature, scaling, coefficient, intercept, and threshold values.
        """
        return {
            "feature_names": list(self.feature_names),
            "means": [float(value) for value in self.means],
            "scales": [float(value) for value in self.scales],
            "coefficients": [float(value) for value in self.coefficients],
            "intercept": float(self.intercept),
            "threshold": float(self.threshold),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> LogisticModel:
        """Build a model from a JSON-safe artifact.

        Parameters
        ----------
        payload : dict
            Model artifact.

        Returns
        -------
        LogisticModel
            Reconstructed model.
        """
        names = payload.get("feature_names", [])
        means = payload.get("means", [])
        scales = payload.get("scales", [])
        coefficients = payload.get("coefficients", [])
        if not all(isinstance(item, list) for item in (names, means, scales, coefficients)):
            raise ValueError("invalid model artifact")
        name_values = [str(item) for item in names] if isinstance(names, list) else []
        mean_values = [float(item) for item in means] if isinstance(means, list) else []
        scale_values = [float(item) for item in scales] if isinstance(scales, list) else []
        coefficient_values = (
            [float(item) for item in coefficients] if isinstance(coefficients, list) else []
        )
        intercept_obj = payload.get("intercept")
        threshold_obj = payload.get("threshold")
        return cls(
            feature_names=tuple(name_values),
            means=np.asarray(mean_values, dtype=np.float64),
            scales=np.asarray(scale_values, dtype=np.float64),
            coefficients=np.asarray(coefficient_values, dtype=np.float64),
            intercept=float(intercept_obj) if isinstance(intercept_obj, (int, float, str)) else 0.0,
            threshold=float(threshold_obj) if isinstance(threshold_obj, (int, float, str)) else 0.5,
        )


def fit_logistic(
    features: NDArray[np.float64],
    labels: NDArray[np.bool_],
    *,
    feature_names: tuple[str, ...] = FEATURE_NAMES,
    l2: float = 1.0,
    max_iter: int = 300,
) -> LogisticModel:
    """Fit a balanced L2 logistic-regression model.

    Parameters
    ----------
    features : numpy.ndarray
        Feature matrix.
    labels : numpy.ndarray of bool
        ``True`` means conifer.
    feature_names : tuple of str
        Feature order.
    l2 : float
        L2 penalty strength.
    max_iter : int
        Optimizer iteration limit.

    Returns
    -------
    LogisticModel
        Fitted model.
    """
    matrix = np.asarray(features, dtype=np.float64)
    target = np.asarray(labels, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[1] != len(feature_names):
        raise ValueError("features do not match feature_names")
    if target.shape != (matrix.shape[0],):
        raise ValueError("labels must have one value per row")
    means = matrix.mean(axis=0)
    scales = matrix.std(axis=0)
    scales[scales < 1e-9] = 1.0
    standardized = (matrix - means) / scales
    positives = float(target.sum())
    negatives = float(len(target) - positives)
    if positives <= 0 or negatives <= 0:
        raise ValueError("both classes are required")
    sample_weights = np.where(
        target > 0, len(target) / (2.0 * positives), len(target) / (2.0 * negatives)
    )

    def objective(beta: NDArray[np.float64]) -> float:
        linear = standardized @ beta[:-1] + beta[-1]
        loss = np.sum(sample_weights * (np.logaddexp(0.0, linear) - target * linear))
        return float(loss + 0.5 * l2 * np.dot(beta[:-1], beta[:-1]))

    def gradient(beta: NDArray[np.float64]) -> NDArray[np.float64]:
        linear = standardized @ beta[:-1] + beta[-1]
        residual = sample_weights * (expit(linear) - target)
        grad = np.empty_like(beta)
        grad[:-1] = standardized.T @ residual + l2 * beta[:-1]
        grad[-1] = residual.sum()
        return grad

    result = minimize(
        objective,
        np.zeros(len(feature_names) + 1, dtype=np.float64),
        jac=gradient,
        method="L-BFGS-B",
        options={"maxiter": max_iter},
    )
    if not result.success:
        raise RuntimeError(f"logistic fit failed: {result.message}")
    beta = np.asarray(result.x, dtype=np.float64)
    return LogisticModel(
        feature_names=feature_names,
        means=means,
        scales=scales,
        coefficients=beta[:-1],
        intercept=float(beta[-1]),
    )


def wilson_interval(
    successes: int, total: int, *, z: float = 1.959963984540054
) -> tuple[float, float]:
    """Return a Wilson score interval for a binomial proportion.

    Parameters
    ----------
    successes : int
        Positive count.
    total : int
        Trial count.
    z : float
        Normal quantile.

    Returns
    -------
    tuple of float
        Lower and upper bounds.
    """
    if total <= 0:
        return (0.0, 0.0)
    proportion = successes / total
    denominator = 1.0 + z * z / total
    centre = (proportion + z * z / (2.0 * total)) / denominator
    margin = (
        z
        * math.sqrt(proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total))
        / denominator
    )
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def confusion_matrix(
    labels: NDArray[np.bool_],
    predictions: NDArray[np.bool_],
) -> dict[str, object]:
    """Return a labelled 2x2 confusion matrix.

    Parameters
    ----------
    labels : numpy.ndarray of bool
        True conifer indicator.
    predictions : numpy.ndarray of bool
        Predicted conifer indicator.

    Returns
    -------
    dict
        Matrix, counts, and labels.
    """
    true = np.asarray(labels, dtype=np.bool_)
    predicted = np.asarray(predictions, dtype=np.bool_)
    conifer_true = int(np.sum(true))
    deciduous_true = int(np.sum(~true))
    return {
        "labels": ["conifer", "deciduous"],
        "matrix": [
            [int(np.sum(true & predicted)), int(np.sum(true & ~predicted))],
            [int(np.sum(~true & predicted)), int(np.sum(~true & ~predicted))],
        ],
        "true_conifer": conifer_true,
        "true_deciduous": deciduous_true,
        "predicted_conifer": int(np.sum(predicted)),
        "predicted_deciduous": int(np.sum(~predicted)),
    }


def classification_metrics(
    labels: NDArray[np.bool_],
    predictions: NDArray[np.bool_],
    *,
    bootstrap: int = 400,
    seed: int = 20261106,
) -> dict[str, object]:
    """Calculate accuracy, per-class precision/recall/F1, intervals, and calibration.

    Parameters
    ----------
    labels : numpy.ndarray of bool
        True conifer indicator.
    predictions : numpy.ndarray of bool
        Predicted conifer indicator.
    bootstrap : int
        Number of stratified F1 bootstrap resamples; zero disables.
    seed : int
        Bootstrap seed.

    Returns
    -------
    dict
        Confusion matrix, point estimates, Wilson intervals, Brier score, and calibration.
    """
    true = np.asarray(labels, dtype=np.bool_)
    predicted = np.asarray(predictions, dtype=np.bool_)
    matrix = confusion_matrix(true, predicted)
    tn, fp, fn, tp = (
        int(np.sum(~true & ~predicted)),
        int(np.sum(~true & predicted)),
        int(np.sum(true & ~predicted)),
        int(np.sum(true & predicted)),
    )
    total = len(true)
    accuracy = (tp + tn) / total if total else 0.0
    precision_conifer = tp / (tp + fp) if tp + fp else 0.0
    recall_conifer = tp / (tp + fn) if tp + fn else 0.0
    precision_deciduous = tn / (tn + fn) if tn + fn else 0.0
    recall_deciduous = tn / (tn + fp) if tn + fp else 0.0
    f1_conifer = (
        2 * precision_conifer * recall_conifer / (precision_conifer + recall_conifer)
        if precision_conifer + recall_conifer
        else 0.0
    )
    f1_deciduous = (
        2 * precision_deciduous * recall_deciduous / (precision_deciduous + recall_deciduous)
        if precision_deciduous + recall_deciduous
        else 0.0
    )
    return {
        "matrix": matrix["matrix"],
        "labels": matrix["labels"],
        "n": total,
        "class_counts": {"conifer": int(true.sum()), "deciduous": int((~true).sum())},
        "accuracy": round(accuracy, 4),
        "accuracy_ci95": [round(value, 4) for value in wilson_interval(tp + tn, total)],
        "conifer": {
            "precision": round(precision_conifer, 4),
            "precision_ci95": [round(value, 4) for value in wilson_interval(tp, tp + fp)],
            "recall": round(recall_conifer, 4),
            "recall_ci95": [round(value, 4) for value in wilson_interval(tp, tp + fn)],
            "f1": round(f1_conifer, 4),
        },
        "deciduous": {
            "precision": round(precision_deciduous, 4),
            "precision_ci95": [round(value, 4) for value in wilson_interval(tn, tn + fn)],
            "recall": round(recall_deciduous, 4),
            "recall_ci95": [round(value, 4) for value in wilson_interval(tn, tn + fp)],
            "f1": round(f1_deciduous, 4),
        },
        "bootstrap_f1_ci95": _bootstrap_f1(true, predicted, bootstrap=bootstrap, seed=seed),
    }


def _bootstrap_f1(
    labels: NDArray[np.bool_],
    predictions: NDArray[np.bool_],
    *,
    bootstrap: int,
    seed: int,
) -> dict[str, list[float]]:
    """Bootstrap F1 intervals separately for each class."""
    if bootstrap <= 0:
        return {"conifer": [0.0, 0.0], "deciduous": [0.0, 0.0]}
    rng = np.random.default_rng(seed)
    conifer_values: list[float] = []
    deciduous_values: list[float] = []
    for _ in range(bootstrap):
        indices = rng.integers(0, len(labels), len(labels))
        metrics = classification_metrics(labels[indices], predictions[indices], bootstrap=0)
        conifer_metrics = metrics["conifer"]
        deciduous_metrics = metrics["deciduous"]
        if isinstance(conifer_metrics, dict) and isinstance(deciduous_metrics, dict):
            conifer_values.append(float(conifer_metrics["f1"]))
            deciduous_values.append(float(deciduous_metrics["f1"]))
    return {
        "conifer": [
            round(float(np.percentile(conifer_values, 2.5)), 4),
            round(float(np.percentile(conifer_values, 97.5)), 4),
        ],
        "deciduous": [
            round(float(np.percentile(deciduous_values, 2.5)), 4),
            round(float(np.percentile(deciduous_values, 97.5)), 4),
        ],
    }


def calibration_table(
    probabilities: NDArray[np.float64],
    labels: NDArray[np.bool_],
    *,
    bins: int = 10,
) -> list[dict[str, float | int]]:
    """Return a reliability table for conifer probabilities.

    Parameters
    ----------
    probabilities : numpy.ndarray
        Conifer probabilities.
    labels : numpy.ndarray of bool
        True conifer indicator.
    bins : int
        Number of equal-width probability bins.

    Returns
    -------
    list of dict
        Bin range, count, mean predicted probability, observed frequency.
    """
    values = np.asarray(probabilities, dtype=np.float64)
    truth = np.asarray(labels, dtype=np.float64)
    rows: list[dict[str, float | int]] = []
    edges = np.linspace(0.0, 1.0, bins + 1)
    for index in range(bins):
        low = float(edges[index])
        high = float(edges[index + 1])
        selected = (values >= low) & (values < high if index < bins - 1 else values <= high)
        count = int(selected.sum())
        if count:
            rows.append(
                {
                    "low": round(low, 3),
                    "high": round(high, 3),
                    "count": count,
                    "mean_probability": round(float(values[selected].mean()), 4),
                    "observed_frequency": round(float(truth[selected].mean()), 4),
                }
            )
    return rows


def block_ids(
    x: NDArray[np.float64], y: NDArray[np.float64], *, size_m: float = 500.0
) -> NDArray[np.int64]:
    """Return deterministic spatial block identifiers.

    Parameters
    ----------
    x, y : numpy.ndarray
        Projected coordinates.
    size_m : float
        Block side in metres.

    Returns
    -------
    numpy.ndarray
        Integer block identifiers.
    """
    columns = np.floor(np.asarray(x) / size_m).astype(np.int64)
    rows = np.floor(np.asarray(y) / size_m).astype(np.int64)
    offset = int(np.min(rows)) - 1 if rows.size else 0
    return (rows - offset) * 100_000 + columns


def holdout_mask(
    blocks: NDArray[np.int64],
    *,
    fraction: float = 0.25,
    seed: str = "p35-2026-11-06",
) -> NDArray[np.bool_]:
    """Return a deterministic block holdout mask.

    Parameters
    ----------
    blocks : numpy.ndarray
        Block identifiers.
    fraction : float
        Approximate holdout fraction.
    seed : str
        Hash seed.

    Returns
    -------
    numpy.ndarray of bool
        ``True`` for held-out blocks.
    """
    mask = np.zeros(len(blocks), dtype=np.bool_)
    for index, block in enumerate(blocks):
        digest = hashlib.sha256(f"{seed}:{int(block)}".encode()).digest()
        mask[index] = int.from_bytes(digest[:4], "big") / 2**32 < fraction
    return mask


def brier_score(probabilities: NDArray[np.float64], labels: NDArray[np.bool_]) -> float:
    """Return the Brier score for conifer probabilities.

    Parameters
    ----------
    probabilities : numpy.ndarray
        Conifer probabilities.
    labels : numpy.ndarray of bool
        True conifer indicator.

    Returns
    -------
    float
        Mean squared probability error.
    """
    values = np.asarray(probabilities, dtype=np.float64)
    truth = np.asarray(labels, dtype=np.float64)
    return round(float(np.mean((values - truth) ** 2)), 6)


def feature_names() -> tuple[str, ...]:
    """Return the model feature names.

    Returns
    -------
    tuple of str
        Feature names.
    """
    return FEATURE_NAMES


def as_feature_matrix(rows: Sequence[Sequence[float]]) -> NDArray[np.float64]:
    """Convert feature rows to a validated matrix.

    Parameters
    ----------
    rows : sequence of sequence of float
        Feature rows.

    Returns
    -------
    numpy.ndarray
        Feature matrix.
    """
    matrix = np.asarray(rows, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[1] != len(FEATURE_NAMES):
        raise ValueError("feature matrix does not match the model feature count")
    return matrix
