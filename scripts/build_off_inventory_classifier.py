#!/usr/bin/env python3
"""Train and evaluate the P35 conifer/deciduous classifier from public inventories."""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from pyproj import Transformer

from fresh_urban_forest.classifier import (
    FEATURE_NAMES,
    LogisticModel,
    block_ids,
    brier_score,
    calibration_table,
    classification_metrics,
    fit_logistic,
    holdout_mask,
)
from fresh_urban_forest.terrain import project_lonlat

ROOT = Path("data/processed")
LCC = Path("data/tmp/lcc_tif/LCC2020/LCC2020.tif")
LCC_CRS = "EPSG:26910"
PROJECTED_CRS = "EPSG:3157"
LABEL_CITIES = ("vancouver_2022", "surrey_2025")
TRAIN_CITIES = ("vancouver", "surrey")
UNLABELED_CITIES = ("burnaby_2022", "coquitlam_2025")
LCC_CONIFER = {6, 15}
LCC_DECIDUOUS = {7, 16}
LCC_SHRUB = {8}


@dataclass(frozen=True, slots=True)
class TrainingRow:
    """One labelled training record."""

    city: str
    tree_id: str
    features: tuple[float, ...]
    conifer: bool
    lcc_class: int
    x_m: float
    y_m: float


def _read_map_trees(slug: str) -> list[dict[str, Any]]:  # pragma: no cover - operator I/O path
    """Read the all-tree GeoJSON properties for one instance.

    Parameters
    ----------
    slug : str
        Dataset slug.

    Returns
    -------
    list of dict
        GeoJSON features.
    """
    path = ROOT / slug / "map_trees.json.gz"
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    features = payload.get("features", [])
    return [feature for feature in features if isinstance(feature, dict)]


def _sample_lcc(  # pragma: no cover - operator I/O path
    lon: np.ndarray,
    lat: np.ndarray,
    *,
    source: Path = LCC,
) -> np.ndarray:
    """Sample Metro LCC classes at WGS84 points.

    Parameters
    ----------
    lon, lat : numpy.ndarray
        WGS84 coordinates.
    source : Path
        LCC GeoTIFF.

    Returns
    -------
    numpy.ndarray
        LCC class codes, zero outside the raster.
    """
    transformer = Transformer.from_crs("EPSG:4326", LCC_CRS, always_xy=True)
    x, y = transformer.transform(lon, lat)
    with rasterio.open(source) as dataset:
        array = dataset.read(1)
        cols = np.floor((x - dataset.bounds.left) / dataset.transform.a).astype(int)
        rows = np.floor((dataset.bounds.top - y) / abs(dataset.transform.e)).astype(int)
    values = np.zeros(len(lon), dtype=np.uint8)
    valid = (cols >= 0) & (cols < array.shape[1]) & (rows >= 0) & (rows < array.shape[0])
    values[valid] = array[rows[valid], cols[valid]]
    return values


def _feature_vector(  # pragma: no cover - operator I/O path
    height: float,
    crown_width: float,
    dbh: float,
    crown_ratio: float,
    lcc_class: int,
) -> tuple[float, ...]:
    """Build the shared feature vector for one tree or candidate.

    Parameters
    ----------
    height : float
        Height in metres.
    crown_width : float
        Crown width in metres.
    dbh : float
        Diameter at breast height in centimetres.
    crown_ratio : float
        Live-crown ratio.
    lcc_class : int
        Metro LCC class code. It is retained in the call contract for label-independent
        context but is intentionally **not** a model feature.

    Returns
    -------
    tuple of float
        Feature vector in ``FEATURE_NAMES`` order.
    """
    h = max(float(height), 0.1)
    width = max(float(crown_width), 0.1)
    return (
        h,
        float(np.log1p(h)),
        width,
        h / width,
    )


def _training_rows() -> list[TrainingRow]:  # pragma: no cover - operator I/O path
    """Collect known-good labelled tree rows from Vancouver and Surrey.

    Returns
    -------
    list of TrainingRow
        Feature rows with species-group labels.
    """
    rows: list[TrainingRow] = []
    for slug in LABEL_CITIES:
        features = _read_map_trees(slug)
        lon = np.asarray([float(item["geometry"]["coordinates"][0]) for item in features])
        lat = np.asarray([float(item["geometry"]["coordinates"][1]) for item in features])
        classes = _sample_lcc(lon, lat)
        city = slug.removesuffix("_2022").removesuffix("_2025")
        for item, lcc_class in zip(features, classes, strict=True):
            properties = item.get("properties", {})
            group = str(properties.get("group", "")).lower()
            if group not in {"conifer", "deciduous"}:
                continue
            x, y = project_lonlat(
                float(item["geometry"]["coordinates"][0]),
                float(item["geometry"]["coordinates"][1]),
                PROJECTED_CRS,
            )
            rows.append(
                TrainingRow(
                    city=city,
                    tree_id=str(properties.get("tree_id", "")),
                    features=_feature_vector(
                        float(properties.get("height", 0.0)),
                        float(properties.get("crown_width", 0.0)),
                        float(properties.get("dbh_cm", 0.0)),
                        float(properties.get("crown_ratio", 0.55)),
                        int(lcc_class),
                    ),
                    conifer=group == "conifer",
                    lcc_class=int(lcc_class),
                    x_m=float(x),
                    y_m=float(y),
                )
            )
    return rows


def _weak_label_metrics(  # pragma: no cover - operator I/O path
    model: LogisticModel,
) -> dict[str, object]:
    """Evaluate model agreement with LCC weak labels, not known-good truth.

    Parameters
    ----------
    model : LogisticModel
        Trained model.

    Returns
    -------
    dict
        Weak-label agreement by city.
    """
    output: dict[str, object] = {}
    for slug in UNLABELED_CITIES:
        features = _read_map_trees(slug)
        lon = np.asarray([float(item["geometry"]["coordinates"][0]) for item in features])
        lat = np.asarray([float(item["geometry"]["coordinates"][1]) for item in features])
        classes = _sample_lcc(lon, lat)
        vectors: list[tuple[float, ...]] = []
        weak: list[bool] = []
        for item, lcc_class in zip(features, classes, strict=True):
            if lcc_class not in LCC_CONIFER | LCC_DECIDUOUS:
                continue
            properties = item.get("properties", {})
            vectors.append(
                _feature_vector(
                    float(properties.get("height", 0.0)),
                    float(properties.get("crown_width", 0.0)),
                    float(properties.get("dbh_cm", 0.0)),
                    float(properties.get("crown_ratio", 0.55)),
                    int(lcc_class),
                )
            )
            weak.append(lcc_class in LCC_CONIFER)
        if not vectors:
            continue
        matrix = np.asarray(vectors, dtype=np.float64)
        truth = np.asarray(weak, dtype=np.bool_)
        predicted = model.predict(matrix)
        metrics = classification_metrics(truth, predicted, bootstrap=100)
        metrics["label_kind"] = "LCC weak label; not known-good species inventory"
        output[slug] = metrics
    return output


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - operator path
    """Train the classifier and write the report/model artifacts.

    Parameters
    ----------
    argv : list of str or None
        Command-line arguments.

    Returns
    -------
    int
        Process status.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/processed/lower_mainland_classifier"),
    )
    args = parser.parse_args(argv)
    rows = _training_rows()
    labels = np.asarray([row.conifer for row in rows], dtype=np.bool_)
    matrix = np.asarray([row.features for row in rows], dtype=np.float64)
    blocks = block_ids(
        np.asarray([row.x_m for row in rows], dtype=np.float64),
        np.asarray([row.y_m for row in rows], dtype=np.float64),
    )
    held_out = holdout_mask(blocks)
    train = (~held_out) & np.asarray([row.city in TRAIN_CITIES for row in rows], dtype=np.bool_)
    test = held_out
    model = fit_logistic(matrix[train], labels[train])
    test_probabilities = model.predict_proba(matrix[test])
    test_predictions = test_probabilities >= model.threshold
    pooled = classification_metrics(labels[test], test_predictions, bootstrap=400)
    pooled["brier_score"] = brier_score(test_probabilities, labels[test])
    pooled["calibration"] = calibration_table(test_probabilities, labels[test])
    by_city = {}
    for city in sorted({row.city for row in rows}):
        mask = np.asarray([row.city == city for row in rows], dtype=np.bool_) & test
        if mask.sum() == 0:
            continue
        probabilities = model.predict_proba(matrix[mask])
        by_city[city] = classification_metrics(
            labels[mask],
            probabilities >= model.threshold,
            bootstrap=100,
        )
        by_city[city]["brier_score"] = brier_score(probabilities, labels[mask])
    final_mask = np.asarray([row.city in TRAIN_CITIES for row in rows], dtype=np.bool_)
    final_model = fit_logistic(matrix[final_mask], labels[final_mask])
    weak = _weak_label_metrics(final_model)
    report = {
        "schema_version": "fresh-urban-forest.classifier-report.v1",
        "model_family": "standardized L2 logistic regression, balanced class weights",
        "feature_names": list(FEATURE_NAMES),
        "threshold": 0.5,
        "known_good_labels": {
            "available_cities": ["Vancouver", "Surrey"],
            "training_cities": ["Vancouver", "Surrey"],
            "external_test_city": None,
            "unavailable_cities": ["Burnaby", "Coquitlam"],
            "label_source": "Public tree inventories; species-group labels",
            "note": (
                "The model is fitted on Vancouver and Surrey structural features with "
                "spatial block holdout. Surrey heights are imputed from land cover, so its "
                "result is a weaker test. Burnaby and Coquitlam have no public species "
                "inventory, so they cannot contribute a known-good confusion matrix yet."
            ),
        },
        "training": {
            "rows": len(rows),
            "cities": sorted({row.city for row in rows}),
            "conifer": int(labels.sum()),
            "deciduous": int((~labels).sum()),
            "spatial_block_m": 500,
            "train_rows": int(train.sum()),
            "test_rows": int(test.sum()),
        },
        "evaluation": pooled,
        "by_city": by_city,
        "weak_label_agreement": weak,
        "model": final_model.to_dict(),
        "caveats": [
            "Public inventory labels are known-good relative to the inventory, not a field audit.",
            "Surrey heights are imputed from LCC classes; its test is weaker than Vancouver.",
            "LCC class is a context feature, not an independent species observation.",
            "Burnaby/Coquitlam weak-label agreement is not accuracy against field truth.",
            "Candidates remain screening trees, not a census or ownership layer.",
        ],
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "model.json").write_text(
        json.dumps(final_model.to_dict(), indent=2) + "\n", encoding="utf-8"
    )
    (args.out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for slug in (*LABEL_CITIES, *UNLABELED_CITIES):
        root = ROOT / slug
        if root.is_dir():
            shutil.copyfile(args.out / "report.json", root / "classifier_report.json")
    accuracy = pooled["accuracy"]
    accuracy_value = float(accuracy) if isinstance(accuracy, (int, float)) else 0.0
    print(
        f"trained on {len(rows)} labelled trees; test {int(test.sum())}; "
        f"accuracy {accuracy_value:.3f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
