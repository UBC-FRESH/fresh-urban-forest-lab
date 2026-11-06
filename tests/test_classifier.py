"""Tests for the off-inventory conifer/deciduous classifier and QA metrics."""

from __future__ import annotations

import numpy as np

from fresh_urban_forest.classifier import (
    LogisticModel,
    brier_score,
    calibration_table,
    classification_metrics,
    confusion_matrix,
    fit_logistic,
    holdout_mask,
    wilson_interval,
)


def test_wilson_interval_is_bounded() -> None:
    """The Wilson interval stays in [0, 1] and contains the estimate."""
    low, high = wilson_interval(80, 100)
    assert 0.0 <= low < 0.8 < high <= 1.0


def test_confusion_matrix_and_metrics() -> None:
    """A deterministic toy matrix produces the expected counts."""
    truth = np.asarray([True, True, False, False, True, False], dtype=np.bool_)
    predicted = np.asarray([True, False, False, True, True, False], dtype=np.bool_)
    matrix = confusion_matrix(truth, predicted)
    assert matrix["matrix"] == [[2, 1], [1, 2]]
    metrics = classification_metrics(truth, predicted, bootstrap=10)
    assert metrics["n"] == 6
    accuracy = metrics["accuracy"]
    assert isinstance(accuracy, (int, float))
    assert 0.0 <= float(accuracy) <= 1.0
    assert "accuracy_ci95" in metrics
    assert "bootstrap_f1_ci95" in metrics


def test_logistic_model_round_trip_and_prediction() -> None:
    """The tiny model learns a separable synthetic signal and serializes."""
    rng = np.random.default_rng(7)
    conifer = rng.normal(loc=2.0, scale=0.4, size=(80, 4))
    deciduous = rng.normal(loc=-2.0, scale=0.4, size=(80, 4))
    features = np.vstack([conifer, deciduous])
    labels = np.asarray([True] * 80 + [False] * 80)
    model = fit_logistic(features, labels, l2=0.1)
    assert np.mean(model.predict(features) == labels) > 0.9
    restored = LogisticModel.from_dict(model.to_dict())
    assert np.allclose(restored.predict_proba(features), model.predict_proba(features))


def test_holdout_brier_and_calibration() -> None:
    """Spatial holdout is deterministic; calibration and Brier are finite."""
    blocks = np.asarray([1, 1, 2, 2, 3, 3], dtype=np.int64)
    first = holdout_mask(blocks)
    second = holdout_mask(blocks)
    assert np.array_equal(first, second)
    probabilities = np.asarray([0.1, 0.9, 0.8, 0.2])
    truth = np.asarray([False, True, True, False], dtype=np.bool_)
    assert brier_score(probabilities, truth) < 0.05
    table = calibration_table(probabilities, truth, bins=4)
    assert table
    assert all(0.0 <= float(row["observed_frequency"]) <= 1.0 for row in table)
