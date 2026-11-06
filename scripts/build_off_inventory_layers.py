#!/usr/bin/env python3
"""Build P35 off-inventory layers and model predictions for three city instances."""

from __future__ import annotations

import argparse
import gzip
import json
import math
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import rasterio
from affine import Affine
from numpy.typing import NDArray
from pyproj import Transformer
from rasterio.warp import Resampling, reproject
from scipy.spatial import cKDTree

from fresh_urban_forest.classifier import LogisticModel
from fresh_urban_forest.lower_mainland import (
    GridSpec,
    canopy_records_from_classes,
    class_species,
    grid_for_bounds,
)
from fresh_urban_forest.terrain import project_lonlat

ROOT = Path("data/processed")
LCC = Path("data/tmp/lcc_tif/LCC2020/LCC2020.tif")
CRS = "EPSG:3157"
MODEL = ROOT / "lower_mainland_classifier" / "model.json"
REPORT = ROOT / "lower_mainland_classifier" / "report.json"
TREE_CLASSES = {6, 7, 15, 16}
SURREY_SLUG = "surrey_2025"
UNLABELED = {
    "burnaby_2022": "burnaby_lidar_2022",
    "coquitlam_2025": "metro_lcc_2020",
}


def _map_trees(slug: str) -> list[dict[str, Any]]:  # pragma: no cover - operator I/O path
    """Read all tree features for one instance."""
    with gzip.open(ROOT / slug / "map_trees.json.gz", "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [item for item in payload.get("features", []) if isinstance(item, dict)]


def _lcc_grid(  # pragma: no cover - operator I/O path
    boundary_path: Path,
    *,
    resolution_m: float,
) -> tuple[GridSpec, NDArray[np.uint8]]:
    """Reproject LCC tree classes to a city grid."""
    frame = gpd.read_file(boundary_path).to_crs(CRS)
    grid = grid_for_bounds(
        (
            float(frame.total_bounds[0]),
            float(frame.total_bounds[1]),
            float(frame.total_bounds[2]),
            float(frame.total_bounds[3]),
        ),
        resolution_m=resolution_m,
    )
    with rasterio.open(LCC) as source:
        classes = np.zeros((grid.height, grid.width), dtype=np.uint8)
        reproject(
            source=rasterio.band(source, 1),
            destination=classes,
            src_transform=source.transform,
            src_crs=source.crs,
            src_nodata=0,
            dst_transform=Affine(
                grid.resolution_m, 0.0, grid.left, 0.0, -grid.resolution_m, grid.top
            ),
            dst_crs=CRS,
            dst_nodata=0,
            resampling=Resampling.nearest,
        )
    return grid, classes


def _sample_lcc(  # pragma: no cover - operator I/O path
    lon: NDArray[np.float64],
    lat: NDArray[np.float64],
) -> NDArray[np.uint8]:
    """Sample LCC class at WGS84 points."""
    with rasterio.open(LCC) as dataset:
        transformer = Transformer.from_crs("EPSG:4326", dataset.crs, always_xy=True)
        x, y = transformer.transform(lon, lat)
        array = dataset.read(1)
        cols = np.floor((x - dataset.bounds.left) / dataset.transform.a).astype(int)
        rows = np.floor((dataset.bounds.top - y) / abs(dataset.transform.e)).astype(int)
        values = np.zeros(len(lon), dtype=np.uint8)
        valid = (cols >= 0) & (cols < array.shape[1]) & (rows >= 0) & (rows < array.shape[0])
        values[valid] = array[rows[valid], cols[valid]]
    return values


def _features(  # pragma: no cover - operator I/O path
    height: float,
    crown_width: float,
) -> tuple[float, float, float, float]:
    """Return the four structural model features."""
    h = max(float(height), 0.1)
    width = max(float(crown_width), 0.1)
    return (h, float(math.log1p(h)), width, h / width)


def _candidate(  # pragma: no cover - operator I/O path
    *,
    candidate_id: str,
    lon: float,
    lat: float,
    x: float,
    y: float,
    height: float,
    crown_width: float,
    group: str,
    probability: float,
    confidence: float,
    nearest: float,
    inventory_status: str,
) -> dict[str, Any]:
    """Build one candidate record."""
    return {
        "candidate_id": candidate_id,
        "detected_id": candidate_id,
        "lon": round(lon, 7),
        "lat": round(lat, 7),
        "x_m": round(x, 2),
        "y_m": round(y, 2),
        "height_m": round(height, 2),
        "crown_radius_m": round(crown_width / 2.0, 2),
        "crown_area_m2": round(math.pi * (crown_width / 2.0) ** 2, 1),
        "nearest_inventory_m": round(nearest, 2),
        "land_class": "unknown",
        "confidence": round(confidence, 3),
        "predicted_group": group,
        "conifer_probability": round(probability, 4),
        "group_confidence": round(abs(probability - 0.5) * 2.0, 4),
        "inventory_status": inventory_status,
        "reasons": [
            f"height {height:.1f} m",
            f"crown width {crown_width:.1f} m",
            f"model conifer probability {probability:.2f}",
            inventory_status,
        ],
    }


def _surrey_candidates(  # pragma: no cover - operator I/O path
    model: LogisticModel,
) -> list[dict[str, Any]]:
    """Build off-inventory candidates for Surrey from LCC canopy maxima."""
    grid, classes = _lcc_grid(ROOT / SURREY_SLUG / "boundary.geojson", resolution_m=5.0)
    public = _map_trees(SURREY_SLUG)
    public_xy = np.asarray(
        [
            project_lonlat(
                float(item["geometry"]["coordinates"][0]),
                float(item["geometry"]["coordinates"][1]),
                CRS,
            )
            for item in public
        ],
        dtype=np.float64,
    )
    tree_index = cKDTree(public_xy)
    records = canopy_records_from_classes(classes, grid, step_m=20.0)
    candidates: list[dict[str, Any]] = []
    for record in records:
        x = float(record.x_m or 0.0)
        y = float(record.y_m or 0.0)
        nearest, _ = tree_index.query(np.asarray([x, y]), k=1)
        if nearest < 5.0:
            continue
        height = float(record.height_m or 2.0)
        crown_width = float(record.crown_width_m or 1.0)
        features = np.asarray([_features(height, crown_width)], dtype=np.float64)
        probability = float(model.predict_proba(features)[0])
        predicted = "conifer" if probability >= 0.5 else "deciduous"
        confidence = 0.5 * abs(probability - 0.5) * 2.0 + 0.5 * min(float(nearest) / 20.0, 1.0)
        from fresh_urban_forest.terrain import unproject_xy

        lon, lat = unproject_xy(x, y, CRS)
        candidates.append(
            _candidate(
                candidate_id=f"surrey-off-{len(candidates) + 1:07d}",
                lon=lon,
                lat=lat,
                x=x,
                y=y,
                height=height,
                crown_width=crown_width,
                group=predicted,
                probability=probability,
                confidence=confidence,
                nearest=float(nearest),
                inventory_status="outside_public_inventory",
            )
        )
    return candidates


def _unlabelled_candidates(  # pragma: no cover - operator I/O path
    slug: str,
    source: str,
    model: LogisticModel,
) -> list[dict[str, Any]]:
    """Build off-inventory candidates from a city with no public inventory."""
    features = _map_trees(slug)
    lon = np.asarray([float(item["geometry"]["coordinates"][0]) for item in features])
    lat = np.asarray([float(item["geometry"]["coordinates"][1]) for item in features])
    classes = _sample_lcc(lon, lat)
    candidates: list[dict[str, Any]] = []
    for item, lcc_class in zip(features, classes, strict=True):
        properties = item.get("properties", {})
        height = max(float(properties.get("height", 0.0)), 1.0)
        crown_width = max(float(properties.get("crown_width", 0.0)), 0.8)
        vector = np.asarray([_features(height, crown_width)], dtype=np.float64)
        probability = float(model.predict_proba(vector)[0])
        predicted = "conifer" if probability >= 0.5 else "deciduous"
        x, y = project_lonlat(
            float(item["geometry"]["coordinates"][0]),
            float(item["geometry"]["coordinates"][1]),
            CRS,
        )
        candidates.append(
            _candidate(
                candidate_id=f"{slug}-off-{len(candidates) + 1:07d}",
                lon=float(item["geometry"]["coordinates"][0]),
                lat=float(item["geometry"]["coordinates"][1]),
                x=x,
                y=y,
                height=height,
                crown_width=crown_width,
                group=predicted,
                probability=probability,
                confidence=0.5 + 0.5 * abs(probability - 0.5) * 2.0,
                nearest=0.0,
                inventory_status="no_public_inventory",
            )
        )
        _ = (source, lcc_class, class_species(int(lcc_class)))
    return candidates


def _write_city(  # pragma: no cover - operator I/O path
    slug: str,
    candidates: list[dict[str, Any]],
    model_report: dict[str, Any],
) -> None:
    """Write summary, GeoJSON, and compact 3D arrays for one city."""
    root = ROOT / slug
    high = [item for item in candidates if float(item["confidence"]) >= 0.6]
    summary = {
        "schema_version": "fresh-urban-forest.off-inventory.classifier.v1",
        "dataset_id": slug,
        "candidate_count": len(candidates),
        "high_confidence_count": len(high),
        "candidate_area_m2": round(sum(float(item["crown_area_m2"]) for item in candidates), 1),
        "detected_count": len(candidates),
        "matched_count": 0,
        "unmatched_inventory_count": 0,
        "land_classes": {"unknown": len(candidates)},
        "inventory_status": {
            status: sum(1 for item in candidates if item["inventory_status"] == status)
            for status in sorted({item["inventory_status"] for item in candidates})
        },
        "confidence_p50": (
            round(float(np.median([float(item["confidence"]) for item in candidates])), 3)
            if candidates
            else 0.0
        ),
        "confidence_p95": (
            round(
                float(np.percentile([float(item["confidence"]) for item in candidates], 95)),
                3,
            )
            if candidates
            else 0.0
        ),
        "method": (
            "LCC/structure candidates scored by the P35 logistic classifier; "
            "known-good labels from Vancouver and Surrey public inventories."
        ),
        "classifier": {
            "model_family": model_report.get("model_family"),
            "training": model_report.get("training"),
            "known_good_evaluation": model_report.get("evaluation"),
            "label_limits": model_report.get("known_good_labels"),
        },
        "evidence": {
            "tier": "screening",
            "caveat": (
                "Candidate trees are not a census or ownership layer. Conifer/deciduous "
                "predictions are screening probabilities, not field species IDs."
            ),
        },
    }
    (root / "off_inventory.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [item["lon"], item["lat"]]},
            "properties": {
                key: item[key]
                for key in (
                    "candidate_id",
                    "height_m",
                    "crown_radius_m",
                    "crown_area_m2",
                    "confidence",
                    "predicted_group",
                    "conifer_probability",
                    "group_confidence",
                    "inventory_status",
                    "land_class",
                    "nearest_inventory_m",
                )
            },
        }
        for item in candidates
    ]
    with gzip.open(root / "off_inventory.geojson.gz", "wt", encoding="utf-8") as handle:
        json.dump(
            {"type": "FeatureCollection", "features": features},
            handle,
            separators=(",", ":"),
        )
    land_code = 4
    compact = {
        "schema_version": "fresh-urban-forest.off-inventory.3d.v2",
        "count": len(high),
        "confidence_floor": 0.6,
        "x_m": [float(item["x_m"]) for item in high],
        "y_m": [float(item["y_m"]) for item in high],
        "height_m": [float(item["height_m"]) for item in high],
        "crown_radius_m": [float(item["crown_radius_m"]) for item in high],
        "land_code": [land_code for _ in high],
        "group_code": [0 if item["predicted_group"] == "conifer" else 1 for item in high],
        "confidence": [float(item["confidence"]) for item in high],
    }
    with gzip.open(root / "off_inventory_3d.json.gz", "wt", encoding="utf-8") as handle:
        json.dump(compact, handle, separators=(",", ":"))
    print(f"{slug}: {len(candidates)} candidates; {len(high)} high confidence")


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - operator path
    """Build all P35 off-inventory layers.

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
    parser.parse_args(argv)
    model_payload = json.loads(MODEL.read_text(encoding="utf-8"))
    model = LogisticModel.from_dict(model_payload)
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    surrey = _surrey_candidates(model)
    _write_city(SURREY_SLUG, surrey, report)
    for slug, source in UNLABELED.items():
        candidates = _unlabelled_candidates(slug, source, model)
        _write_city(slug, candidates, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
